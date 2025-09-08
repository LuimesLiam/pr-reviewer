import asyncio
import json
import os
import logging
from typing import List, Dict, Any
from langgraph.graph import START, END, StateGraph
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langgraph.types import Command
from langchain_core.prompts import ChatPromptTemplate

from Agents.Models.BaseLLM import BaseLLM
from Agents.Models.llm_factory import llm_factory

from Models.State import State, ReviewComment
from Services.Git.git_factory import git_service_factory
from Services.Git.AbstractGitService import AbstractGitService

# --- Logging Setup ---
logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.DEBUG,
                        format='[%(asctime)s] %(levelname)s %(name)s:%(lineno)d | %(message)s')

# --- Configuration (env overridable) ---
MODEL_REVIEW_TIMEOUT_SECONDS = int(
    os.getenv("MODEL_REVIEW_TIMEOUT_SECONDS", "180"))
MAX_PATCH_CHARS = int(os.getenv("MAX_PATCH_CHARS", "20000"))
MAX_CONTEXT_ROUNDS = int(os.getenv("MAX_CONTEXT_ROUNDS", "3"))
GRAPH_RECURSION_LIMIT = min(
    int(os.getenv("GRAPH_RECURSION_LIMIT", "300")), 2000)


def _truncate(val: Any, length: int = 500) -> str:
    try:
        s = str(val)
    except Exception:
        return '<unstringable>'
    if len(s) <= length:
        return s
    return s[:length] + f"... <truncated {len(s)-length} chars>"


class Reviewer:

    def __init__(self, model: BaseLLM):
        self.model = model
        logger.debug("Initializing Reviewer with model=%s",
                     type(model).__name__)
        self.git_service: AbstractGitService = git_service_factory("github")
        logger.debug("Git service instantiated: %s",
                     type(self.git_service).__name__)
        self.review_prompt = self._create_review_prompt()
        self.context_request_prompt = self._create_context_request_prompt()
        logger.debug("Prompts created (review_prompt vars=%s, context_prompt vars=%s)",
                     self.review_prompt.input_variables, self.context_request_prompt.input_variables)

    def _create_review_prompt(self) -> ChatPromptTemplate:
        logger.debug("Creating review prompt template")
        # Curly braces for JSON examples are escaped with double braces so that
        # ChatPromptTemplate only treats {instructions}, {diff_patch}, {context_files}
        # as variables.
        template = """
You are an expert code reviewer.
You are reviewing ONE diff from a pull request.
You ONLY see the patch for this file plus any additional context files provided.
If you have ENOUGH information to provide feedback, return a JSON object per schema.
If you do NOT have enough information (e.g. referenced functions/classes not shown or architectural context missing), instead return a JSON object requesting files.

Schema for feedback mode (mode = 'feedback'):
{{
  "mode": "feedback",
  "file_name": string,
  "review_comment": string,
  "requires_rework": boolean,
  "suggested_improvements_markdown": string
}}

Schema for context request (mode = 'request_context'):
{{
  "mode": "request_context",
  "file_name": string,               // current diff filename
  "reason": string,                  // why more context is needed
  "requested_files": [ string, ... ] // list of file paths to fetch next (limit 5)
}}

Return ONLY valid JSON. No markdown fences. No explanations outside JSON.

Primary review instructions:
{instructions}

Current diff patch (unified format):
```
{diff_patch}
```

Additional context files provided:
{context_files}
"""
        return ChatPromptTemplate.from_template(template)

    def _create_context_request_prompt(self) -> ChatPromptTemplate:
        logger.debug("Creating context request prompt template")
        template = """
Given the current file patch and previously supplied context files, decide if more context is still required. If yes, output request_context JSON (same schema). If no, output feedback JSON.

Return ONLY JSON.

File: {file_name}
Patch:
```
{diff_patch}
```
Context files:
{context_files}
"""
        return ChatPromptTemplate.from_template(template)

    async def load_instructions(self) -> str:
        logger.debug("Loading instructions")
        instructions_dir = os.path.join(
            os.path.dirname(__file__), "Instructions")
        parts = []
        for fname in ["general.txt", "PythonSet.txt", "dotnetSet.txt"]:
            path = os.path.join(instructions_dir, fname)
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        content = f.read().strip()
                        parts.append(content)
                        logger.debug(
                            "Loaded instruction file %s (%d chars)", fname, len(content))
                except Exception as e:
                    logger.warning(
                        "Failed reading instruction file %s: %s", fname, e)
            else:
                logger.debug("Instruction file missing: %s", fname)
        result = "\n\n".join(parts)
        logger.debug("Aggregated instructions length=%d", len(result))
        return result

    async def fetch_diffs(self, state: State) -> Command:
        logger.debug("fetch_diffs called with state keys=%s",
                     list(state.keys()))
        q = state.get("event_queue")
        repo = state.get("repo_name")
        pr = state.get("pr_number")
        logger.info("Fetching diffs for repo=%s pr=%s", repo, pr)
        if q:
            await q.put(f"▶️ Fetching diffs for {repo} PR #{pr}")
        pr_data = await self.git_service.get_pull_request(repo, pr)
        logger.debug("PR data type=%s keys=%s", type(pr_data).__name__, list(
            pr_data.keys()) if isinstance(pr_data, dict) else 'n/a')
        diffs = pr_data.get("diffs", []) if isinstance(pr_data, dict) else []
        logger.info("Fetched %d diffs", len(diffs))
        if q:
            await q.put(f"📂 {len(diffs)} diffs fetched")
        messages = list(state.get("messages", []))
        messages.append(AIMessage(content=f"Loaded {len(diffs)} diffs"))
        return Command(update={
            "diffs": diffs,
            "current_diff_index": 0,
            "additional_context": {},
            "pending_context_request": [],
            "context_round": 0,
            "messages": messages
        }, goto="review_single_diff")

    async def _build_context_section(self, additional_context: Dict[str, str]) -> str:
        logger.debug("Building context section for %d files",
                     len(additional_context))
        if not additional_context:
            return "(none)"
        sections = []
        for path, content in additional_context.items():
            snippet = content[:1500]  # truncate to control prompt size
            logger.debug("Context file included path=%s size=%d truncated_to=%d", path, len(
                content), len(snippet))
            sections.append(f"--- {path} ---\n{snippet}")
        joined = "\n\n".join(sections)
        logger.debug("Context section total length=%d", len(joined))
        return joined

    def _parse_model_json(self, raw_content: Any) -> Dict[str, Any] | None:
        logger.debug("Parsing model JSON from type=%s",
                     type(raw_content).__name__)
        if isinstance(raw_content, dict):
            logger.debug("Raw content already dict with keys=%s",
                         list(raw_content.keys()))
            return raw_content
        text = getattr(raw_content, "content", raw_content)
        if not isinstance(text, str):
            logger.warning("Model output not string-like: %s", type(text))
            return None
        text = text.strip()
        logger.debug("Model raw text length=%d preview=%s",
                     len(text), _truncate(text, 120))
        # Try direct JSON
        try:
            parsed = json.loads(text)
            logger.debug("Parsed JSON directly with keys=%s",
                         list(parsed.keys()))
            return parsed
        except Exception as e:
            logger.debug("Direct JSON parse failed: %s", e)
        # Try to locate first JSON object by braces
        try:
            first = text.index('{')
            last = text.rindex('}')
            candidate = text[first:last+1]
            parsed = json.loads(candidate)
            logger.debug("Parsed JSON via slicing with keys=%s",
                         list(parsed.keys()))
            return parsed
        except Exception as e:
            logger.warning("Failed to parse model output as JSON: %s", e)
            return None

    async def review_single_diff(self, state: State) -> Command:
        logger.debug("review_single_diff invoked")
        q = state.get("event_queue")
        idx = state.get("current_diff_index", 0)
        diffs = state.get("diffs", [])
        logger.debug("Current diff index=%d total_diffs=%d", idx, len(diffs))
        if idx >= len(diffs):
            logger.info("All diffs processed; moving to completion")
            return Command(goto="complete_review", update={})
        diff_obj = diffs[idx] if isinstance(diffs, list) else {}
        file_name = str(diff_obj.get("filename", "unknown"))
        patch = diff_obj.get("patch") or "(no patch available)"
        if q:
            try:
                await q.put(f"🔍 Reviewing {idx+1}/{len(diffs)}: {file_name}")
            except Exception:  # safety
                pass
        patch_for_model = patch
        if len(patch_for_model) > MAX_PATCH_CHARS:
            truncated_len = len(patch_for_model) - MAX_PATCH_CHARS
            patch_for_model = patch_for_model[:MAX_PATCH_CHARS] + \
                f"\n... <truncated {truncated_len} chars>"
            if q:
                await q.put(f"⚠️ Patch truncated for {file_name} (original {len(patch)} chars, truncated {truncated_len} chars)")
        logger.info("Reviewing diff index=%d file=%s patch_len=%d used_len=%d",
                    idx, file_name, len(patch), len(patch_for_model))
        additional_context = state.get("additional_context", {})
        instructions = await self.load_instructions()
        context_section = await self._build_context_section(additional_context)
        logger.debug("Invoking model for file=%s context_files=%d instructions_len=%d timeout=%ds",
                     file_name, len(additional_context), len(instructions), MODEL_REVIEW_TIMEOUT_SECONDS)
        try:
            response = await asyncio.wait_for(
                self.model._invoke(
                    self.review_prompt,
                    instructions=instructions,
                    diff_patch=patch_for_model,
                    context_files=context_section
                ),
                timeout=MODEL_REVIEW_TIMEOUT_SECONDS
            )
            logger.debug("Model response type=%s", type(response).__name__)
        except asyncio.TimeoutError:
            logger.warning("Model timeout after %ds for file=%s; skipping with fallback review",
                           MODEL_REVIEW_TIMEOUT_SECONDS, file_name)
            if q:
                await q.put(f"⏱️ Model timeout for {file_name}; skipping with fallback review")
            fallback_comment: ReviewComment = ReviewComment(
                file_name=file_name,
                review_comment=f"Model timed out after {MODEL_REVIEW_TIMEOUT_SECONDS}s while reviewing this diff. Consider manually inspecting this file.",
                requires_rework=False,
                suggested_improvements_markdown=""
            )
            existing = list(state.get("review_comments", []))
            existing.append(fallback_comment)
            messages = list(state.get("messages", []))
            messages.append(AIMessage(content=json.dumps(fallback_comment)))
            return Command(update={
                "review_comments": existing,
                "current_diff_index": idx + 1,
                "additional_context": {},
                "pending_context_request": [],
                "context_round": 0,
                "messages": messages
            }, goto="review_single_diff")
        except Exception as e:
            logger.exception(
                "Model invocation error for file=%s: %s", file_name, e)
            response = AIMessage(
                content=f"{{\"mode\": \"feedback\", \"file_name\": \"{file_name}\", \"review_comment\": \"Model invocation error: {str(e).replace('\\"', '\\\"')}\", \"requires_rework\": false, \"suggested_improvements_markdown\": \"\"}}")
        parsed = self._parse_model_json(response)
        if not parsed:
            if q:
                await q.put(f"⚠️ Model returned unparseable output for {file_name}; skipping")
            logger.warning(
                "Unparseable model output for file=%s; skipping to next diff", file_name)
            messages = list(state.get("messages", []))
            messages.append(
                AIMessage(content=f"Could not parse review for {file_name}"))
            return Command(update={
                "current_diff_index": idx + 1,
                "additional_context": {},
                "pending_context_request": [],
                "context_round": 0,
                "messages": messages
            }, goto="review_single_diff")
        mode = parsed.get("mode")
        logger.debug("Parsed model mode=%s keys=%s", mode, list(parsed.keys()))
        messages = list(state.get("messages", []))
        # Enforce context round limit
        current_context_round = state.get("context_round", 0)
        if mode == "request_context" and current_context_round >= MAX_CONTEXT_ROUNDS:
            logger.info("Context round limit reached for file=%s (round=%d >= %d); forcing feedback fallback",
                        file_name, current_context_round, MAX_CONTEXT_ROUNDS)
            if q:
                await q.put(f"⚠️ Context round limit reached for {file_name}; proceeding with partial review")
            parsed = {
                "mode": "feedback",
                "file_name": file_name,
                "review_comment": (parsed.get("reason") or "Context limit reached; partial review provided with available information."),
                "requires_rework": False,
                "suggested_improvements_markdown": ""
            }
            mode = "feedback"
        if mode == "request_context":
            requested = [str(r) for r in parsed.get("requested_files", [])][:5]
            reason = parsed.get("reason", "")
            logger.info("Model requested context for file=%s files=%s reason=%s",
                        file_name, requested, _truncate(reason, 200))
            if q:
                await q.put(f"📄 Context requested for {file_name}: {requested} ({reason})")
            messages.append(
                AIMessage(content=f"Context requested for {file_name}: {requested}"))
            return Command(update={
                "pending_context_request": requested,
                "context_round": current_context_round + 1,
                "messages": messages
            }, goto="fetch_additional_context")
        review_comment: ReviewComment = ReviewComment(
            file_name=file_name,
            review_comment=str(parsed.get("review_comment", "")),
            requires_rework=bool(parsed.get("requires_rework", False)),
            suggested_improvements_markdown=str(
                parsed.get("suggested_improvements_markdown", ""))
        )
        logger.info(
            "Completed review for file=%s requires_rework=%s comment_len=%d improvements_len=%d", file_name, review_comment["requires_rework"], len(review_comment["review_comment"]), len(review_comment["suggested_improvements_markdown"]))
        existing = list(state.get("review_comments", []))
        existing.append(review_comment)
        if q:
            await q.put(f"✅ Review completed for {file_name}")
        messages.append(AIMessage(content=json.dumps(review_comment)))
        return Command(update={
            "review_comments": existing,
            "current_diff_index": idx + 1,
            "additional_context": {},
            "pending_context_request": [],
            "context_round": 0,
            "messages": messages
        }, goto="review_single_diff")

    async def fetch_additional_context(self, state: State) -> Command:
        logger.debug("fetch_additional_context invoked")
        q = state.get("event_queue")
        repo = state.get("repo_name")
        pr = state.get("pr_number")
        pending = state.get("pending_context_request", [])
        logger.info(
            "Fetching additional context repo=%s pr=%s pending_files=%s", repo, pr, pending)
        additional_context = dict(state.get("additional_context", {}))
        fetched = []
        for path in pending:
            if path in additional_context:
                logger.debug("Skipping already-fetched context file=%s", path)
                continue
            try:
                file_content = await self.git_service.get_file_from_pull_request(repo, pr, path)
                if isinstance(file_content, dict):
                    additional_context[path] = file_content.get(
                        "decoded_content", "")
                    fetched.append(path)
                    logger.debug("Fetched file=%s size=%d", path,
                                 len(additional_context[path]))
                else:
                    logger.warning("Unexpected file content type for %s: %s", path, type(
                        file_content).__name__)
            except Exception as e:
                logger.warning(
                    "Failed to fetch requested file=%s error=%s", path, e)
                # Try fuzzy find candidates
                try:
                    candidates = await self.git_service.find_file_in_pr(repo, pr, path)
                except Exception:
                    candidates = []
                if candidates:
                    resolved = None
                    for cand in candidates:
                        try:
                            file_content = await self.git_service.get_file_from_pull_request(repo, pr, cand)
                            if isinstance(file_content, dict):
                                additional_context[cand] = file_content.get(
                                    "decoded_content", "")
                                fetched.append(cand)
                                resolved = cand
                                logger.debug(
                                    "Fuzzy-resolved %s -> %s", path, cand)
                                break
                        except Exception:
                            continue
                    if resolved is None and q:
                        await q.put(f"⚠️ Unable to fetch requested file: {path}")
                else:
                    if q:
                        await q.put(f"⚠️ Unable to fetch requested file: {path}")
        if q and fetched:
            await q.put(f"📥 Fetched additional context files: {fetched}")
        messages = list(state.get("messages", []))
        if fetched:
            messages.append(AIMessage(content=f"Fetched context: {fetched}"))
        logger.info("Additional context fetch complete fetched=%s", fetched)
        return Command(update={
            "additional_context": additional_context,
            "pending_context_request": [],
            "messages": messages
        }, goto="review_single_diff")

    async def complete_review(self, state: State) -> Command:
        logger.info("Completing review process")
        q = state.get("event_queue")
        summary_lines = []
        for rc in state.get("review_comments", []):
            summary_lines.append(
                f"- {rc['file_name']}: {'REWORK' if rc['requires_rework'] else 'OK'}")
        if not summary_lines:
            summary_lines.append("(No review comments generated)")
        summary_text = "Review Summary:\n" + "\n".join(summary_lines)
        if q:
            try:
                await q.put(summary_text)
                await q.put("__COMPLETE__")
            except Exception:
                logger.warning("Failed pushing completion events to queue")
        messages = list(state.get("messages", []))
        messages.append(AIMessage(content=summary_text))
        logger.debug("Total review comments=%d", len(
            state.get("review_comments", [])))
        return Command(update={"messages": messages}, goto=END)


class ReviewerHandler:
    async def async_init(self):
        logger.debug("ReviewerHandler.async_init start")
        self.model = llm_factory("gemini")
        logger.debug("Model instantiated: %s", type(self.model).__name__)
        self.reviewerModel = Reviewer(model=self.model)

        graph_builder = StateGraph(state_schema=State)
        logger.debug("StateGraph initialized with schema=%s", State)

        # Nodes
        graph_builder.add_node("fetch_diffs", self.reviewerModel.fetch_diffs)
        graph_builder.add_node("review_single_diff",
                               self.reviewerModel.review_single_diff)
        graph_builder.add_node("fetch_additional_context",
                               self.reviewerModel.fetch_additional_context)
        graph_builder.add_node(
            "complete_review", self.reviewerModel.complete_review)
        logger.debug("Graph nodes added")

        # Only the initial edge; subsequent transitions are controlled via Command.goto
        graph_builder.add_edge(START, "fetch_diffs")
        logger.debug("Initial edge added START->fetch_diffs")

        self.reviewer_graph = graph_builder.compile()
        logger.debug("Graph compiled")

    async def run(self, repo_name: str, pr_number: int, event_queue: asyncio.Queue[str]):
        logger.info("ReviewerHandler.run invoked repo=%s pr=%s",
                    repo_name, pr_number)
        initial_state = State(
            repo_name=repo_name,
            pr_number=pr_number,
            event_queue=event_queue,
            review_comments=[],
            grouped_files={},  # legacy
            messages=[HumanMessage(
                content=f"Review PR #{pr_number} for {repo_name}")],
            diffs=[],
            current_diff_index=0,
            additional_context={},
            pending_context_request=[],
            context_round=0,
        )
        logger.debug("Initial state prepared keys=%s",
                     list(initial_state.keys()))
        logger.debug(
            "Invoking reviewer_graph with recursion_limit=%d", GRAPH_RECURSION_LIMIT)
        result = await self.reviewer_graph.ainvoke(input=initial_state, config={"recursion_limit": GRAPH_RECURSION_LIMIT})
        logger.info("Reviewer graph execution complete")
        # Attempt to push final structured review comments
        if event_queue:
            try:
                final_comments = result.get(
                    "review_comments", []) if isinstance(result, dict) else []
                if final_comments:
                    await event_queue.put(json.dumps({"review_comments": final_comments}))
            except Exception as e:
                logging.debug(
                    "Could not push final review comments JSON: %s", e)
        return result
