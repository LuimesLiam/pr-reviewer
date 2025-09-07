import asyncio
import json
import os
import ast
import re
from typing import List
from langgraph.graph import START, END, StateGraph
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langgraph.types import Command
from langchain_core.prompts import ChatPromptTemplate

from Agents.Models.BaseLLM import BaseLLM
from Agents.Models.llm_factory import llm_factory

from Models.State import State, ReviewComment
from Services.Git.git_factory import git_service_factory
from Services.Git.AbstractGitService import AbstractGitService


class Reviewer:

    def __init__(self, model: BaseLLM):
        self.model = model
        self.git_service: AbstractGitService = git_service_factory("github")
        self.review_prompt = self._create_review_prompt()

    def _create_review_prompt(self) -> ChatPromptTemplate:
        template = """
You are an expert code reviewer. You are reviewing a pull request.
Return ONLY a single JSON object that matches the provided schema. Do NOT wrap it in markdown fences. Do NOT add explanations.
Here are related file diffs that should be reviewed together:

{file_group}

Provide a JSON object with keys: file_name, review_comment, requires_rework, suggested_improvements_markdown.
"""
        return ChatPromptTemplate.from_template(template)

    async def get_grouped_files(self, state: State) -> Command:
        """
        Get the files from the pull request and group them.
        """
        q = state.get("event_queue")
        repo_name = state.get("repo_name")
        pr_number = state.get("pr_number")

        if q:
            await q.put(f"▶️  Fetching files for {repo_name} #{pr_number}")

        files = await self.git_service.group_files_in_pull_request(repo_name, pr_number)

        num_files = len(files) if files else 0
        if q:
            await q.put(f"📂 Found {num_files} files in PR #{pr_number}")

        messages = list(state.get("messages", []))
        messages.append(AIMessage(content=f"Found {num_files} files."))

        return Command(
            update={
                "grouped_files": files or {},
                "messages": messages,
            },
            goto="review_files"
        )

    async def review_files(self, state: State) -> Command:
        """
        Review each group of files in the pull request together.
        """
        q = state.get("event_queue")
        grouped_files = state.get("grouped_files", [])
        review_comments: List[ReviewComment] = []
        all_messages: List[BaseMessage] = list(state.get("messages", []))

        # Define the expected schema for structured output
        review_schema = {
            "title": "FileReview",
            "description": "Review output for a file or group of files in a pull request.",
            "type": "object",
            "properties": {
                "file_name": {"type": "string", "description": "Name(s) of the file(s) reviewed."},
                "review_comment": {"type": "string", "description": "Overall review comment for the file(s)."},
                "requires_rework": {"type": "boolean", "description": "True if the file group requires rework."},
                "suggested_improvements_markdown": {"type": "string", "description": "Markdown formatted suggestions for improvement."}
            },
            "required": ["file_name", "review_comment", "requires_rework", "suggested_improvements_markdown"]
        }

        def _coerce_review_dict(d: dict) -> ReviewComment:
            # If model wrapped fields under an 'args' key (e.g. {"type":"FileReview","args":{...}}), unwrap it.
            if 'args' in d and isinstance(d['args'], dict):
                d = d['args']
            return ReviewComment(
                file_name=str(d.get("file_name", "unknown")),
                review_comment=str(d.get("review_comment", "")),
                requires_rework=bool(d.get("requires_rework", False)),
                suggested_improvements_markdown=str(
                    d.get("suggested_improvements_markdown", ""))
            )

        def _balanced_brace_extract(text: str, start_index: int) -> str | None:
            depth = 0
            start = None
            for i in range(start_index, len(text)):
                ch = text[i]
                if ch == '{':
                    if start is None:
                        start = i
                    depth += 1
                elif ch == '}':
                    if depth > 0:
                        depth -= 1
                        if depth == 0 and start is not None:
                            return text[start:i+1]
            return None

        def _extract_args_section(raw: str) -> dict | None:
            # Look for 'args': { ... }
            for token in ["'args'", '"args"']:
                idx = raw.find(token)
                if idx != -1:
                    brace_idx = raw.find('{', idx)
                    if brace_idx != -1:
                        snippet = _balanced_brace_extract(raw, brace_idx)
                        if snippet:
                            # Try JSON first
                            try:
                                return json.loads(snippet)
                            except Exception:
                                # Fallback to literal_eval
                                try:
                                    return ast.literal_eval(snippet)
                                except Exception:
                                    pass
            return None

        def _extract_first_object_with_keys(raw: str) -> dict | None:
            # Find substring containing required keys and attempt extraction
            required_keys = ["file_name", "review_comment",
                             "requires_rework", "suggested_improvements_markdown"]
            if all(k in raw for k in required_keys):
                # Attempt to locate earliest '{' before first key
                first_key_pos = min(raw.find(k)
                                    for k in required_keys if raw.find(k) != -1)
                prefix = raw.rfind('{', 0, first_key_pos)
                if prefix != -1:
                    snippet = _balanced_brace_extract(raw, prefix)
                    if snippet:
                        try:
                            return json.loads(snippet)
                        except Exception:
                            try:
                                return ast.literal_eval(snippet)
                            except Exception:
                                pass
            return None

        def _regex_key_extract(raw: str) -> dict:
            # More permissive extraction of quoted string values, including multi-line until next key
            result = {}
            patterns = {
                "file_name": r"file_name['\"]?\s*[:=]\s*['\"]([^'\"]*)['\"]",
                "review_comment": r"review_comment['\"]?\s*[:=]\s*['\"]([^'\"]*)['\"]",
                "requires_rework": r"requires_rework['\"]?\s*[:=]\s*(True|False|true|false|1|0)",
                "suggested_improvements_markdown": r"suggested_improvements_markdown['\"]?\s*[:=]\s*['\"]([\s\S]*?)['\"]\s*(?:,|}\n|}\r|}$)"
            }
            for k, pat in patterns.items():
                m = re.search(pat, raw)
                if m:
                    val = m.group(1)
                    if k == "requires_rework":
                        result[k] = val.lower() in ("true", "1")
                    else:
                        result[k] = val
            return result

        def _parse_response(resp) -> List[ReviewComment]:
            parsed: List[ReviewComment] = []
            # Direct types
            if isinstance(resp, dict):
                parsed.append(_coerce_review_dict(resp))
                return parsed
            if isinstance(resp, list):
                for item in resp:
                    if isinstance(item, dict):
                        parsed.append(_coerce_review_dict(item))
                if parsed:
                    return parsed
            # Extract content
            content = getattr(resp, "content", resp)
            if not isinstance(content, str):
                return parsed
            raw = content.strip()
            # Try full JSON
            try:
                loaded = json.loads(raw)
                return _parse_response(loaded)
            except Exception:
                pass
            # args section
            args_dict = _extract_args_section(raw)
            if args_dict and all(k in args_dict for k in ["file_name", "review_comment", "requires_rework", "suggested_improvements_markdown"]):
                return [_coerce_review_dict(args_dict)]
            # Attempt first object with keys
            obj_with_keys = _extract_first_object_with_keys(raw)
            if obj_with_keys:
                return [_coerce_review_dict(obj_with_keys)]
            # Extract JSON-like portion
            try:
                first_brace = raw.index('{')
                last_brace = raw.rindex('}')
                candidate = raw[first_brace:last_brace+1]
                try:
                    loaded = json.loads(candidate)
                    return _parse_response(loaded)
                except Exception:
                    try:
                        loaded = ast.literal_eval(candidate)
                        return _parse_response(loaded)
                    except Exception:
                        pass
            except ValueError:
                pass
            # Regex fallback
            fallback = _regex_key_extract(raw)
            if fallback:
                parsed.append(_coerce_review_dict(fallback))
            return parsed

        # Read instructions from files
        instructions_dir = os.path.join(
            os.path.dirname(__file__), "Instructions")
        python_instructions = ""
        dotnet_instructions = ""
        general_instructions = ""
        try:
            with open(os.path.join(instructions_dir, "PythonSet.txt"), "r") as f:
                python_instructions = f.read().strip()
        except Exception:
            pass
        try:
            with open(os.path.join(instructions_dir, "dotnetSet.txt"), "r") as f:
                dotnet_instructions = f.read().strip()
        except Exception:
            pass
        try:
            with open(os.path.join(instructions_dir, "general.txt"), "r") as f:
                general_instructions = f.read().strip()
        except Exception:
            pass

        for group in grouped_files:
            if q:
                await q.put(f"🔍 Reviewing a group of {len(group)} files...")

            # Determine which instructions to include
            include_python = any(file_info.get(
                "file_path", "").endswith(".py") for file_info in group)
            include_dotnet = any(file_info.get(
                "file_path", "").endswith(".cs") for file_info in group)

            instructions = []
            if general_instructions:
                instructions.append(general_instructions)
            if include_python and python_instructions:
                instructions.append(python_instructions)
            if include_dotnet and dotnet_instructions:
                instructions.append(dotnet_instructions)
            # Add explicit JSON-only directive
            instructions.append(
                "Return ONLY valid JSON. No markdown, no commentary.")
            instructions_str = "\n\n".join(instructions)

            # Preprocess and combine file diffs
            file_entries = []
            for file_info in group:
                file_name = file_info.get("file_path")
                old_diff = file_info.get("old_diff", "") or ""
                new_diff = file_info.get("new_diff", "") or ""
                entry = f"file: {file_name}\nold diff:\n{old_diff}\nnew diff:\n{new_diff}"
                file_entries.append(entry)
            combined_diff = "\n\n".join(file_entries)

            # Format prompt with combined diffs and instructions
            prompt_str = self.review_prompt.format(file_group=combined_diff)
            if instructions_str:
                prompt_str = f"Instructions for this review:\n{instructions_str}\n\n" + prompt_str
            prompt = ChatPromptTemplate.from_messages(
                [HumanMessage(content=prompt_str)])

            # Use structured output invocation
            response = await self.model._invoke_structured_output(
                prompt=prompt,
                schema=review_schema
            )

            try:
                parsed_comments = _parse_response(response)
                if not parsed_comments:
                    raise ValueError(
                        "Unable to parse model response into review comments")
                for rc in parsed_comments:
                    review_comments.append(rc)
                    all_messages.append(AIMessage(content=json.dumps(rc)))
                if q:
                    await q.put(f"✅ Finished reviewing group of files")
            except Exception as e:
                if q:
                    await q.put(f"❌ Error reviewing group of files: {e}")
                all_messages.append(
                    AIMessage(
                        content=f"Error processing review for file group: {e}")
                )

        return Command(
            update={
                "review_comments": review_comments,
                "messages": all_messages
            },
            goto="complete_review"
        )

    async def complete_review(self, state: State) -> Command:
        """
        Complete the review process and return all review comments.
        """
        q = state.get("event_queue")
        if q:
            # Send all review comments as a JSON string to the event stream
            await q.put("__COMPLETE__")

        messages = list(state.get("messages", []))
        messages.append(AIMessage(content="Review completed successfully."))

        # Return all review comments in the final update
        return Command(
            update={
                "messages": messages
            },
            goto=END
        )


class ReviewerHandler:
    async def async_init(self):
        self.model = llm_factory("gemini")
        self.reviewerModel = Reviewer(model=self.model)

        graph_builder = StateGraph(state_schema=State)

        graph_builder.add_node("get_grouped_files",
                               self.reviewerModel.get_grouped_files)
        graph_builder.add_node("review_files", self.reviewerModel.review_files)
        graph_builder.add_node(
            "complete_review", self.reviewerModel.complete_review)

        graph_builder.add_edge(START, "get_grouped_files")
        graph_builder.add_edge("get_grouped_files", "review_files")
        graph_builder.add_edge("review_files", "complete_review")
        graph_builder.add_edge("complete_review", END)

        self.reviewer_graph = graph_builder.compile()

    async def run(self, repo_name: str, pr_number: int, event_queue: asyncio.Queue[str]):
        initial_state = State(
            repo_name=repo_name,
            pr_number=pr_number,
            event_queue=event_queue,
            review_comments=[],
            grouped_files={},
            messages=[HumanMessage(
                content=f"Review PR #{pr_number} for {repo_name}")]
        )

        return await self.reviewer_graph.ainvoke(input=initial_state)
