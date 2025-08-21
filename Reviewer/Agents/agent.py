import asyncio
import json
import os
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
Here are related file diffs that should be reviewed together:

{file_group}

Please provide a review for these files.
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
                # If response is a dict, use it directly
                if isinstance(response, dict):
                    review_comment_obj = ReviewComment(**response)
                # If response has .content, try to parse it
                elif hasattr(response, "content") and isinstance(response.content, str):
                    review_data = json.loads(response.content)
                    review_comment_obj = ReviewComment(**review_data)
                else:
                    raise ValueError("Unexpected response format")

                review_comments.append(review_comment_obj)
                all_messages.append(
                    AIMessage(content=json.dumps(response) if isinstance(
                        response, dict) else response.content)
                )
                if q:
                    await q.put(f"✅ Finished reviewing group of files")

            except Exception as e:
                if q:
                    await q.put(f"❌ Error reviewing group of files: {e}")
                all_messages.append(
                    AIMessage(content=f"Error processing review for file group")
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
