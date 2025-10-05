"""
Example: Extending the Agent Framework reviewer with custom tools.

This demonstrates how to add domain-specific review tools.
"""
import asyncio
import os
from typing import List, Dict, Any
from agent_framework import ChatAgent

from Agent_framework_agent import (
    ReviewerHandler,
    ReviewSingleDiffExecutor,
    CompleteReviewExecutor,
    ReviewState,
    ReviewTools,
    Model,
    BaseModelExecutor
)
from Services.Git.git_factory import git_service_factory


# ============================================================================
# Custom Tools Example
# ============================================================================

class EnhancedReviewTools(ReviewTools):
    """Extended tools with additional review capabilities."""

    async def check_has_tests(self, file_path: str) -> str:
        """Check if a given source file has corresponding tests."""
        # Extract test file path heuristics
        test_patterns = [
            file_path.replace(".py", "_test.py"),
            file_path.replace(".py", ".test.py"),
            file_path.replace("src/", "tests/"),
            file_path.replace(".js", ".test.js"),
            file_path.replace(".ts", ".test.ts"),
        ]

        try:
            changed_files = await self.git_service.get_pr_changed_file_paths(
                self.repo_name, self.pr_number
            )

            found_tests = [p for p in test_patterns if p in changed_files]

            if found_tests:
                return f"✓ Found tests: {', '.join(found_tests)}"
            else:
                return f"⚠️  No tests found for {file_path}. Expected patterns: {', '.join(test_patterns[:2])}"

        except Exception as e:
            return f"Error checking tests: {e}"

    async def check_dependencies(self, file_path: str) -> str:
        """Check if new dependencies were added in package files."""
        if any(pkg in file_path for pkg in ["package.json", "requirements.txt", "go.mod", "Cargo.toml"]):
            try:
                result = await self.git_service.get_file_from_pull_request(
                    self.repo_name, self.pr_number, file_path
                )
                if result and isinstance(result, dict):
                    content = result.get("decoded_content", "")
                    # Simple heuristic: check for common dependency keywords
                    if any(kw in content for kw in ["dependencies", "requires", "dependencies ="]):
                        return f"📦 Dependency file detected. Review new packages carefully for security/licensing."

                return "No dependency changes detected"
            except Exception as e:
                return f"Error checking dependencies: {e}"

        return "Not a dependency file"

    async def find_similar_patterns(self, code_snippet: str) -> str:
        """Find similar code patterns in the PR for consistency checking."""
        # Simplified: Search for similar function signatures or patterns
        try:
            # Extract function name if present
            lines = code_snippet.split('\n')
            func_lines = [
                l for l in lines if 'def ' in l or 'function ' in l or 'const ' in l]

            if func_lines:
                return f"Pattern search: Found function definitions. Consider checking for similar implementations in other files for consistency."

            return "No specific patterns detected"

        except Exception as e:
            return f"Error in pattern search: {e}"

    def get_tools(self):
        """Return all tools including base + enhanced."""
        # Get base tools
        base_tools = super().get_tools()

        # Add enhanced tools with sync wrappers
        def check_has_tests_sync(file_path: str) -> str:
            """Check if a given source file has corresponding tests."""
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.check_has_tests(file_path))

        def check_dependencies_sync(file_path: str) -> str:
            """Check if new dependencies were added in package files."""
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.check_dependencies(file_path))

        def find_similar_patterns_sync(code_snippet: str) -> str:
            """Find similar code patterns in the PR."""
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.find_similar_patterns(code_snippet))

        return base_tools + [
            check_has_tests_sync,
            check_dependencies_sync,
            find_similar_patterns_sync
        ]


# ============================================================================
# Custom Executor with Enhanced Tools
# ============================================================================

class EnhancedReviewExecutor(BaseModelExecutor):
    """Custom executor that uses enhanced tools."""

    def __init__(self, id: str, model: Model, git_service, instructions: str):
        super().__init__(id=id, model=model)
        self.git_service = git_service
        self.instructions = instructions

    async def handle(self, state: ReviewState, ctx):
        """Review with enhanced tools."""
        from agent_framework import WorkflowContext
        from Agents.Models.BaseLLM import BaseLLM
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"Enhanced review of {len(state.diffs)} diffs")

        # Create enhanced tools
        tools_instance = EnhancedReviewTools(
            self.git_service,
            state.repo_name,
            state.pr_number
        )
        tools = tools_instance.get_tools()

        # Update agent with enhanced tools
        self.model.agent = ChatAgent(
            chat_client=self.model.chat_client,
            name=self.model.agent.name,
            instructions=self.instructions + """
            
Additional capabilities:
- Use check_has_tests() to verify test coverage
- Use check_dependencies() for package/dependency files
- Use find_similar_patterns() to find consistency issues
""",
            tools=tools
        )

        from Agent_framework_agent import ReviewComment
        review_comments = []

        for idx, diff in enumerate(state.diffs, 1):
            file_name = diff.get("file_name", "unknown")
            patch = diff.get("patch", "")

            logger.info(
                f"Enhanced review {idx}/{len(state.diffs)}: {file_name}")

            await ctx.set_shared_state("current_status",
                                       f"Enhanced reviewing {file_name} ({idx}/{len(state.diffs)})")

            review_prompt = f"""
Review the following code diff with enhanced analysis.

File: {file_name}

Diff:
```
{patch}
```

Instructions:
{self.instructions}

Use available tools to:
1. Check for test coverage (check_has_tests)
2. Verify dependencies if applicable (check_dependencies)
3. Look for consistency issues (find_similar_patterns)

Then provide structured feedback.
"""

            try:
                result = await self.model.agent.run(
                    review_prompt,
                    response_format=ReviewComment
                )

                review_comment = result.value if hasattr(
                    result, 'value') else result

                if isinstance(review_comment, dict):
                    review_comment["file_name"] = file_name
                    review_obj = ReviewComment(**review_comment)
                elif isinstance(review_comment, ReviewComment):
                    review_comment.file_name = file_name
                    review_obj = review_comment
                else:
                    continue

                review_comments.append(review_obj)
                logger.info(f"Enhanced review complete for {file_name}")

            except Exception as e:
                logger.error(f"Error in enhanced review {file_name}: {e}")
                review_comments.append(ReviewComment(
                    file_name=file_name,
                    review_comment=f"Enhanced review failed: {str(e)}",
                    requires_rework=False,
                    suggested_improvements_markdown=""
                ))

        state.review_comments = review_comments
        await ctx.send_message(state)


# ============================================================================
# Enhanced Handler
# ============================================================================

class EnhancedReviewerHandler(ReviewerHandler):
    """Handler that uses enhanced tools."""

    async def run(self, repo_name: str, pr_number: int):
        """Run enhanced review workflow."""
        from agent_framework import WorkflowBuilder, WorkflowOutputEvent
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"Starting enhanced review for {repo_name} PR #{pr_number}")

        instructions = await self.load_instructions()

        pr_data = await self.git_service.get_pull_request(repo_name, pr_number)
        diffs = pr_data.get("diffs", []) if pr_data else []

        logger.info(f"Found {len(diffs)} diffs for enhanced review")

        initial_state = ReviewState(
            repo_name=repo_name,
            pr_number=pr_number,
            diffs=diffs
        )

        # Create models
        review_model = Model(
            agent_name="EnhancedCodeReviewer",
            instructions=instructions,
            model_id=self.model_id
        )

        summary_model = Model(
            agent_name="EnhancedReviewSummarizer",
            instructions="You are an expert at summarizing code reviews with focus on tests, dependencies, and patterns.",
            model_id=self.model_id
        )

        # Create executors with enhanced tools
        review_executor = EnhancedReviewExecutor(
            id="enhanced_review",
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

        # Run
        result_state = None
        async for event in workflow.run_stream(initial_state):
            logger.debug(f"Event: {type(event).__name__}")
            if isinstance(event, WorkflowOutputEvent):
                result_state = event.data

        logger.info("Enhanced review complete")
        return result_state


# ============================================================================
# Usage Example
# ============================================================================

async def example_enhanced_review():
    """Example of using enhanced review tools."""
    print("=== Enhanced Code Review Example ===\n")

    handler = EnhancedReviewerHandler(model_id="gemini-2.5-flash")

    # Review with enhanced tools
    result = await handler.run(
        repo_name="owner/repo",  # Replace with actual
        pr_number=123
    )

    if result and result.summary:
        print("\n📊 Enhanced Review Summary")
        print("=" * 60)
        print(f"Files reviewed: {result.summary.total_files_reviewed}")
        print(f"Files needing rework: {result.summary.files_requiring_rework}")
        print(f"\nAssessment:\n{result.summary.overall_assessment}")

        print("\n🔍 Enhanced Insights")
        print("=" * 60)
        for comment in result.review_comments:
            print(f"\n📄 {comment.file_name}")
            print(
                f"Status: {'⚠️  Needs Work' if comment.requires_rework else '✅ OK'}")
            print(f"Review: {comment.review_comment}")

            if comment.suggested_improvements_markdown:
                print(f"\n💡 Suggestions:")
                print(comment.suggested_improvements_markdown)


async def demo_tools():
    """Demo individual enhanced tools."""
    print("=== Enhanced Tools Demo ===\n")

    git_service = git_service_factory("github")
    tools = EnhancedReviewTools(
        git_service=git_service,
        repo_name="microsoft/vscode",
        pr_number=12345
    )

    # Demo each tool
    print("1. Checking for tests...")
    result = await tools.check_has_tests("src/vs/base/common/utils.ts")
    print(f"   {result}\n")

    print("2. Checking dependencies...")
    result = await tools.check_dependencies("package.json")
    print(f"   {result}\n")

    print("3. Finding patterns...")
    code = """
    def calculate_total(items):
        return sum(item.price for item in items)
    """
    result = await tools.find_similar_patterns(code)
    print(f"   {result}\n")


if __name__ == "__main__":
    import sys

    print("\nEnhanced Agent Framework Reviewer")
    print("=" * 60)
    print("\nOptions:")
    print("1. Run enhanced review")
    print("2. Demo enhanced tools")
    print("3. Exit")

    choice = input("\nEnter choice (1-3): ").strip()

    if choice == "1":
        asyncio.run(example_enhanced_review())
    elif choice == "2":
        asyncio.run(demo_tools())
    else:
        print("Goodbye!")
