import asyncio
import os
import logging
from typing import List, Dict, Any
from pydantic import BaseModel
from agent_framework import ChatAgent
from agent_framework import Executor, WorkflowBuilder, WorkflowContext, WorkflowOutputEvent, handler
from typing_extensions import Never

from . Models.BaseModels import Model, BaseModelExecutor
from Services.Git.git_factory import git_service_factory
from Services.Git.AbstractGitService import AbstractGitService

# --- Logging Setup ---
logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.DEBUG,
                        format='[%(asctime)s] %(levelname)s %(name)s:%(lineno)d | %(message)s')


# --- Pydantic Models for Structured Output ---
class ReviewComment(BaseModel):
    """Structured review comment for a single file."""
    file_name: str
    review_comment: str
    requires_rework: bool
    suggested_improvements_markdown: str


class ReviewSummary(BaseModel):
    """Summary of all reviews."""
    total_files_reviewed: int
    files_requiring_rework: int
    overall_assessment: str
    key_issues: List[str]


# --- Workflow State ---
class ReviewState(BaseModel):
    """State passed through the workflow."""
    repo_name: str
    pr_number: int
    diffs: List[Dict[str, Any]] = []
    review_comments: List[ReviewComment] = []
    summary: ReviewSummary | None = None


# --- Tool Functions for ReAct Agent ---
class ReviewTools:
    """Tools that the ReAct agent can use to gather context."""

    def __init__(self, git_service: AbstractGitService, repo_name: str, pr_number: int):
        self.git_service = git_service
        self.repo_name = repo_name
        self.pr_number = pr_number

    async def get_file_content(self, file_path: str) -> str:
        """Fetch the full content of a file from the PR branch."""
        try:
            result = await self.git_service.get_file_from_pull_request(
                self.repo_name, self.pr_number, file_path
            )
            if result and isinstance(result, dict):
                return result.get("decoded_content", "File not found")
            return "File not found"
        except Exception as e:
            logger.error(f"Error fetching file {file_path}: {e}")
            return f"Error: {str(e)}"

    async def search_related_files(self, search_term: str) -> str:
        """Search for files related to a given term in the PR."""
        try:
            changed_files = await self.git_service.get_pr_changed_file_paths(
                self.repo_name, self.pr_number
            )
            matches = [f for f in changed_files if search_term.lower()
                       in f.lower()]
            return f"Related files: {', '.join(matches)}" if matches else "No related files found"
        except Exception as e:
            logger.error(f"Error searching files: {e}")
            return f"Error: {str(e)}"

    def get_tools(self):
        """Return list of tool functions with sync wrappers for agent_framework."""

        def get_file_content_sync(file_path: str) -> str:
            """Fetch the full content of a file from the PR branch."""
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.get_file_content(file_path))

        def search_related_files_sync(search_term: str) -> str:
            """Search for files related to a given term in the PR."""
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.search_related_files(search_term))

        return [get_file_content_sync, search_related_files_sync]


# --- Executors ---
class ReviewSingleDiffExecutor(BaseModelExecutor):
    """Executor that reviews all diffs using a ReAct agent with tools."""

    def __init__(self, id: str, model: Model, git_service: AbstractGitService, instructions: str):
        super().__init__(id=id, model=model)
        self.git_service = git_service
        self.instructions = instructions

    @handler
    async def handle(self, state: ReviewState, ctx: WorkflowContext[ReviewState]):
        """Review each diff with ReAct agent and store results."""
        logger.info(
            f"Starting review of {len(state.diffs)} diffs for PR #{state.pr_number}")

        # Create tools for the agent
        tools_instance = ReviewTools(
            self.git_service, state.repo_name, state.pr_number)
        tools = tools_instance.get_tools()

        # Update agent with tools
        self.model.agent = ChatAgent(
            chat_client=self.model.chat_client,
            name=self.model.agent.name,
            instructions=self.instructions,
            tools=tools
        )

        review_comments = []

        # Process each diff
        for idx, diff in enumerate(state.diffs, 1):
            file_name = diff.get("file_name", "unknown")
            patch = diff.get("patch", "")

            logger.info(
                f"Reviewing diff {idx}/{len(state.diffs)}: {file_name}")

            # Stream status update
            await ctx.set_shared_state("current_status", f"Reviewing {file_name} ({idx}/{len(state.diffs)})")

            # Prepare prompt for the agent
            review_prompt = f"""
Review the following code diff and provide structured feedback.

File: {file_name}

Diff (unified format):
```
{patch}
```

Instructions:
{self.instructions}

Use the available tools to fetch additional context if needed (e.g., get_file_content, search_related_files).
Then provide your review following the ReviewComment schema.
"""

            try:
                # Run ReAct agent with structured output
                result = await self.model.agent.run(
                    review_prompt,
                    response_format=ReviewComment
                )

                review_comment = result.value if hasattr(
                    result, 'value') else result

                # Ensure file_name is set
                if isinstance(review_comment, dict):
                    review_comment["file_name"] = file_name
                    review_obj = ReviewComment(**review_comment)
                    review_comments.append(review_obj)
                    logger.info(
                        f"Completed review for {file_name}: rework={review_obj.requires_rework}")
                elif isinstance(review_comment, ReviewComment):
                    review_comment.file_name = file_name
                    review_comments.append(review_comment)
                    logger.info(
                        f"Completed review for {file_name}: rework={review_comment.requires_rework}")
                else:
                    logger.error(
                        f"Unexpected result type: {type(review_comment)}")
                    continue

            except Exception as e:
                logger.error(f"Error reviewing {file_name}: {e}")
                # Add error comment
                review_comments.append(ReviewComment(
                    file_name=file_name,
                    review_comment=f"Review failed: {str(e)}",
                    requires_rework=False,
                    suggested_improvements_markdown=""
                ))

        # Update state with reviews
        state.review_comments = review_comments
        await ctx.send_message(state)


class CompleteReviewExecutor(BaseModelExecutor):
    """Executor that summarizes all reviews."""

    @handler
    async def handle(self, state: ReviewState, ctx: WorkflowContext[Never, ReviewState]):
        """Generate a summary of all reviews."""
        logger.info(
            f"Generating summary for {len(state.review_comments)} reviews")

        # Prepare summary prompt
        reviews_text = "\n\n".join([
            f"File: {r.file_name}\nRequires Rework: {r.requires_rework}\nComment: {r.review_comment}"
            for r in state.review_comments
        ])

        summary_prompt = f"""
Analyze the following code reviews and provide a comprehensive summary.

Reviews:
{reviews_text}

Provide a ReviewSummary with:
- Total files reviewed
- Number of files requiring rework
- Overall assessment of the PR quality
- Key issues that need attention
"""

        try:
            result = await self.model.agent.run(
                summary_prompt,
                response_format=ReviewSummary
            )

            summary = result.value if hasattr(result, 'value') else result

            if isinstance(summary, dict):
                state.summary = ReviewSummary(**summary)
            elif isinstance(summary, ReviewSummary):
                state.summary = summary
            else:
                # Fallback summary
                state.summary = ReviewSummary(
                    total_files_reviewed=len(state.review_comments),
                    files_requiring_rework=sum(
                        1 for r in state.review_comments if r.requires_rework),
                    overall_assessment="Summary generation encountered an error",
                    key_issues=[]
                )

            logger.info(
                f"Summary complete: {state.summary.overall_assessment}")

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            # Fallback summary
            state.summary = ReviewSummary(
                total_files_reviewed=len(state.review_comments),
                files_requiring_rework=sum(
                    1 for r in state.review_comments if r.requires_rework),
                overall_assessment=f"Summary generation failed: {str(e)}",
                key_issues=[]
            )

        await ctx.yield_output(state)


# --- Main Review Handler ---
class ReviewerHandlerAgent:
    """Main handler for PR reviews using agent_framework workflow."""

    def __init__(self, model_id: str = "gpt-5-mini"):
        self.model_id = model_id
        self.git_service = git_service_factory("github")

    async def load_instructions(self) -> str:
        """Load review instructions from files."""
        instructions_dir = os.path.join(os.path.dirname(
            __file__), "..", "Agents", "Instructions")
        parts = []
        for fname in ["general.txt", "PythonSet.txt", "dotnetSet.txt"]:
            fpath = os.path.join(instructions_dir, fname)
            if os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8") as f:
                    parts.append(f.read())
        return "\n\n".join(parts)

    async def run(self, repo_name: str, pr_number: int) -> ReviewState | None:
        """Run the complete review workflow."""
        logger.info(f"Starting review for {repo_name} PR #{pr_number}")

        # Load instructions
        instructions = await self.load_instructions()

        # Fetch PR diffs
        pr_data = await self.git_service.get_pull_request(repo_name, pr_number)
        diffs = pr_data.get("diffs", []) if pr_data else []

        logger.info(f"Found {len(diffs)} diffs to review")

        # Initialize state
        initial_state = ReviewState(
            repo_name=repo_name,
            pr_number=pr_number,
            diffs=diffs
        )

        # Create models for each executor
        review_model = Model(
            agent_name="CodeReviewer",
            instructions=instructions,
            model_id=self.model_id
        )

        summary_model = Model(
            agent_name="ReviewSummarizer",
            instructions="You are an expert at summarizing code reviews and identifying key issues.",
            model_id=self.model_id
        )

        # Create executors
        review_executor = ReviewSingleDiffExecutor(
            id="review_diffs",
            model=review_model,
            git_service=self.git_service,
            instructions=instructions
        )

        complete_executor = CompleteReviewExecutor(
            id="complete_review",
            model=summary_model
        )

        # Build workflow
        workflow = (
            WorkflowBuilder()
            .set_start_executor(review_executor)
            .add_edge(review_executor, complete_executor)
            .build()
        )

        # Run workflow
        result_state = None
        async for event in workflow.run_stream(initial_state):
            logger.debug(f"Workflow event: {type(event).__name__}")
            if isinstance(event, WorkflowOutputEvent):
                result_state = event.data

        logger.info("Review workflow completed")
        return result_state


# --- Example Usage ---
async def main():
    """Example usage of the reviewer workflow."""
    handler = ReviewerHandlerAgent()

    # Example: Review a PR
    result = await handler.run(
        repo_name="LuimesLiam/HomeApp",  # Replace with actual repo
        pr_number=1  # Replace with actual PR number
    )

    if result and result.summary:
        print(f"\n=== Review Summary ===")
        print(f"Total files: {result.summary.total_files_reviewed}")
        print(f"Files needing rework: {result.summary.files_requiring_rework}")
        print(f"Overall: {result.summary.overall_assessment}")
        print(f"\nKey Issues:")
        for issue in result.summary.key_issues:
            print(f"  - {issue}")

        print(f"\n=== Individual Reviews ===")
        for comment in result.review_comments:
            print(f"\nFile: {comment.file_name}")
            print(f"Requires Rework: {comment.requires_rework}")
            print(f"Comment: {comment.review_comment}")
            if comment.suggested_improvements_markdown:
                print(
                    f"Suggestions:\n{comment.suggested_improvements_markdown}")
    else:
        print("Review failed or returned no results.")


if __name__ == "__main__":
    asyncio.run(main())
