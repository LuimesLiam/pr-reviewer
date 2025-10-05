"""
Test script for the Agent Framework based code reviewer.
This demonstrates how to use the new ReAct-based review system.
"""
from Agent_framework_agent import ReviewerHandler, ReviewState
import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


async def test_review():
    """Test the review workflow with example data."""
    print("=== Agent Framework Code Review Test ===\n")

    # Initialize the handler
    handler = ReviewerHandler(model_id="gemini-2.5-flash")

    # Example: Review a PR (replace with actual values)
    repo_name = input("Enter repo name (e.g., 'owner/repo'): ").strip()
    if not repo_name:
        repo_name = "microsoft/vscode"  # Default example

    pr_number_input = input("Enter PR number: ").strip()
    if not pr_number_input:
        pr_number = 1
    else:
        pr_number = int(pr_number_input)

    print(f"\nStarting review for {repo_name} PR #{pr_number}...")
    print("This may take a few minutes depending on the PR size.\n")

    try:
        # Run the review
        result = await handler.run(repo_name, pr_number)

        if result and result.summary:
            print("\n" + "="*60)
            print("REVIEW SUMMARY")
            print("="*60)
            print(
                f"Total files reviewed: {result.summary.total_files_reviewed}")
            print(
                f"Files requiring rework: {result.summary.files_requiring_rework}")
            print(f"\nOverall Assessment:")
            print(result.summary.overall_assessment)

            if result.summary.key_issues:
                print(f"\nKey Issues ({len(result.summary.key_issues)}):")
                for i, issue in enumerate(result.summary.key_issues, 1):
                    print(f"{i}. {issue}")

            print("\n" + "="*60)
            print("INDIVIDUAL FILE REVIEWS")
            print("="*60)

            for i, comment in enumerate(result.review_comments, 1):
                print(f"\n[{i}] File: {comment.file_name}")
                print(
                    f"    Requires Rework: {'⚠️  YES' if comment.requires_rework else '✓ NO'}")
                print(f"    Comment: {comment.review_comment}")

                if comment.suggested_improvements_markdown:
                    print(f"    Suggestions:")
                    for line in comment.suggested_improvements_markdown.split('\n'):
                        print(f"      {line}")

            print("\n" + "="*60)
            print("Review completed successfully!")
            print("="*60)
        else:
            print("❌ Review failed or returned no results.")

    except Exception as e:
        print(f"❌ Error during review: {e}")
        import traceback
        traceback.print_exc()


async def test_with_mock_data():
    """Test with mock data for development/testing."""
    print("=== Testing with Mock Data ===\n")

    # Create a mock state for testing
    from Agent_framework_agent import ReviewState

    mock_diffs = [
        {
            "file_name": "src/example.py",
            "patch": """@@ -1,3 +1,5 @@
 def calculate(x, y):
-    return x + y
+    # TODO: Add input validation
+    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
+        raise ValueError("Inputs must be numbers")
+    return x + y"""
        },
        {
            "file_name": "src/utils.py",
            "patch": """@@ -10,5 +10,7 @@
 def process_data(data):
-    return [x * 2 for x in data]
+    # Optimized version
+    result = [x * 2 for x in data if x is not None]
+    return result"""
        }
    ]

    handler = ReviewerHandler()

    # Mock the get_pull_request to return our test data
    original_method = handler.git_service.get_pull_request

    async def mock_get_pr(repo, pr_num):
        return {
            "title": "Test PR",
            "user": "testuser",
            "body": "Test description",
            "head_branch": "feature/test",
            "diffs": mock_diffs
        }

    handler.git_service.get_pull_request = mock_get_pr

    try:
        result = await handler.run("test/repo", 1)

        if result:
            print(f"✓ Mock test completed successfully!")
            print(f"  Reviews generated: {len(result.review_comments)}")
            if result.summary:
                print(
                    f"  Files needing rework: {result.summary.files_requiring_rework}")
        else:
            print("❌ Mock test failed")

    finally:
        # Restore original method
        handler.git_service.get_pull_request = original_method


def main():
    """Main entry point."""
    print("\nAgent Framework Code Reviewer")
    print("="*60)
    print("\nOptions:")
    print("1. Test with real PR (requires GitHub token)")
    print("2. Test with mock data")
    print("3. Exit")

    choice = input("\nEnter choice (1-3): ").strip()

    if choice == "1":
        asyncio.run(test_review())
    elif choice == "2":
        asyncio.run(test_with_mock_data())
    elif choice == "3":
        print("Goodbye!")
    else:
        print("Invalid choice. Exiting.")


if __name__ == "__main__":
    main()
