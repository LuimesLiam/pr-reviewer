# Quick Start Guide

Get started with the Agent Framework code reviewer in 5 minutes.

## Prerequisites

```bash
# Python 3.10+
python --version

# Install dependencies
pip install -r requirements.txt
```

## Setup

1. **Set environment variables**

Create a `.env` file in the project root:

```bash
# Required
GEMINI_API_KEY=your_gemini_api_key_here
GIT_TOKEN=your_github_token_here

# Optional
MODEL_REVIEW_TIMEOUT_SECONDS=180
MAX_PATCH_CHARS=20000
```

2. **Get API Keys**

- **Gemini API Key**: Get from [Google AI Studio](https://makersuite.google.com/app/apikey)
- **GitHub Token**: Create at [GitHub Settings → Developer Settings → Personal Access Tokens](https://github.com/settings/tokens)
  - Needs `repo` scope for private repos, or `public_repo` for public repos

## Quick Test

### Option 1: Mock Data Test (No APIs needed)

```bash
cd /workspaces/Reviewer/MSAFAgent
python test_agent_framework.py
# Choose option 2: Test with mock data
```

This will run a test with pre-defined mock diffs to verify the setup.

### Option 2: Real PR Review

```bash
python test_agent_framework.py
# Choose option 1: Test with real PR
# Enter repo name: owner/repo
# Enter PR number: 123
```

## Basic Usage in Code

### Simple Example

```python
import asyncio
from Agent_framework_agent import ReviewerHandler

async def main():
    # Initialize handler
    handler = ReviewerHandler(model_id="gemini-2.5-flash")

    # Review a PR
    result = await handler.run(
        repo_name="microsoft/vscode",
        pr_number=12345
    )

    # Print summary
    if result and result.summary:
        print(f"Total files: {result.summary.total_files_reviewed}")
        print(f"Files needing work: {result.summary.files_requiring_rework}")
        print(f"Assessment: {result.summary.overall_assessment}")

asyncio.run(main())
```

### With Custom Instructions

```python
from Agent_framework_agent import ReviewerHandler, ReviewState
from Models.BaseModels import Model

async def custom_review():
    handler = ReviewerHandler()

    # Custom instructions
    custom_instructions = """
    Focus on:
    1. Security vulnerabilities
    2. Performance issues
    3. Code duplication

    Be strict on:
    - Input validation
    - Error handling
    """

    # You can modify the handler's instructions loading
    # or create your own Model with custom instructions

    result = await handler.run("owner/repo", 123)
    return result
```

### Processing Results

```python
result = await handler.run("owner/repo", 123)

# Iterate through reviews
for review in result.review_comments:
    if review.requires_rework:
        print(f"⚠️  {review.file_name}")
        print(f"   Issue: {review.review_comment}")
        print(f"   Fix: {review.suggested_improvements_markdown}")
    else:
        print(f"✓ {review.file_name}: OK")

# Check summary
if result.summary:
    print("\nKey Issues:")
    for issue in result.summary.key_issues:
        print(f"- {issue}")
```

## Workflow Visualization

```bash
python visualize_workflow.py
# Choose option 1 to generate diagrams
# Choose option 2 to print Mermaid code
```

This creates:

- `review_workflow.svg` - Vector graphic
- `review_workflow.png` - Raster image
- `review_workflow.pdf` - PDF document
- `review_workflow.dot` - GraphViz source

## Understanding the Output

### ReviewComment Structure

```python
{
    "file_name": "src/example.py",
    "review_comment": "Added input validation which is good...",
    "requires_rework": true,
    "suggested_improvements_markdown": "- Add docstring\n- Add tests"
}
```

### ReviewSummary Structure

```python
{
    "total_files_reviewed": 5,
    "files_requiring_rework": 2,
    "overall_assessment": "PR introduces solid improvements...",
    "key_issues": [
        "Missing input validation",
        "Test coverage gaps"
    ]
}
```

## Common Issues

### Issue: "GEMINI_API_KEY not set"

**Solution**: Make sure your `.env` file is in the correct location and contains:

```bash
GEMINI_API_KEY=your_actual_key_here
```

### Issue: "GitHub API rate limit exceeded"

**Solution**:

- Ensure you're using an authenticated token (GIT_TOKEN)
- Use a token with appropriate scopes
- Wait for rate limit to reset (shown in error message)

### Issue: "Agent takes too long"

**Solution**:

- Reduce patch size: Set `MAX_PATCH_CHARS` to lower value
- Use faster model: Change to `gemini-2.0-flash-thinking-exp-01-21`
- Review smaller PRs first

### Issue: "Module not found"

**Solution**:

```bash
# Make sure you're in the right directory
cd /workspaces/Reviewer/MSAFAgent

# Reinstall dependencies
pip install -r requirements.txt

# Check Python path
export PYTHONPATH=/workspaces/Reviewer:$PYTHONPATH
```

## Performance Tips

1. **Batch Processing**: Review multiple small PRs in parallel
2. **Caching**: Store frequently accessed files locally
3. **Model Selection**: Use faster models for initial reviews
4. **Filtering**: Skip generated files (package-lock.json, etc.)

## Next Steps

- Read [README.md](README.md) for detailed architecture
- See [COMPARISON.md](COMPARISON.md) for LangGraph comparison
- Explore tool customization in `ReviewTools` class
- Add custom executors for specific workflows

## Example: Complete Review Session

```bash
$ python test_agent_framework.py

Agent Framework Code Reviewer
============================================================

Options:
1. Test with real PR (requires GitHub token)
2. Test with mock data
3. Exit

Enter choice (1-3): 1

Enter repo name (e.g., 'owner/repo'): facebook/react
Enter PR number: 28000

Starting review for facebook/react PR #28000...
This may take a few minutes depending on the PR size.

============================================================
REVIEW SUMMARY
============================================================
Total files reviewed: 8
Files requiring rework: 3

Overall Assessment:
The PR introduces valuable performance improvements to the reconciler,
but requires attention to error handling and test coverage.

Key Issues (4):
1. Missing error handling in fast path optimization
2. Type narrowing could be more explicit in renderer interface
3. Test coverage gaps for edge cases in scheduler
4. Performance regression in development mode needs investigation

============================================================
INDIVIDUAL FILE REVIEWS
============================================================

[1] File: packages/react-reconciler/src/ReactFiberWorkLoop.js
    Requires Rework: ⚠️  YES
    Comment: The new fast path optimization looks promising but lacks...
    Suggestions:
      - Add try-catch around fast path
      - Document performance impact
      - Add benchmark results

[2] File: packages/react-reconciler/src/ReactFiberScheduler.js
    Requires Rework: ✓ NO
    Comment: Clean refactoring with good test coverage...

... (more reviews)

============================================================
Review completed successfully!
============================================================
```

## Support

For issues or questions:

1. Check the README.md for architecture details
2. Review COMPARISON.md for design rationale
3. Look at existing agent.py for LangGraph comparison
4. Check agent_framework documentation

Happy reviewing! 🚀
