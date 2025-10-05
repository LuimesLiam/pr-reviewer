# Agent Framework Code Reviewer

A sophisticated code review system built using Microsoft's Agent Framework, featuring ReAct agents with tool-calling capabilities.

## Architecture Overview

This implementation follows the requirements from `agent.py` but leverages the Agent Framework instead of LangGraph:

```
┌─────────────────────────────────────────────────────────┐
│                  ReviewerHandler                         │
│  • Orchestrates the workflow                            │
│  • Loads instructions                                   │
│  • Initializes models and executors                     │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              Workflow (Agent Framework)                  │
│                                                          │
│  ┌───────────────────────────────────────────────┐     │
│  │   ReviewSingleDiffExecutor                     │     │
│  │   • Loops through all diffs                    │     │
│  │   • Uses ReAct agent with tools                │     │
│  │   • Stores reviews in state                    │     │
│  │   • Streams status updates                     │     │
│  └───────────────────────────────────────────────┘     │
│                         │                               │
│                         ▼                               │
│  ┌───────────────────────────────────────────────┐     │
│  │   CompleteReviewExecutor                       │     │
│  │   • Summarizes all reviews                     │     │
│  │   • Generates structured output                │     │
│  └───────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

## Key Features

### 1. **ReAct Agent with Tools** 🛠️

The review agent uses the ReAct (Reasoning + Acting) pattern and has access to tools:

- `get_file_content(file_path)`: Fetch full file contents from the PR
- `search_related_files(search_term)`: Find related files in the PR

The agent can autonomously decide when it needs more context and call these tools.

### 2. **Structured Output** 📋

Uses Pydantic models for type-safe, structured responses:

```python
class ReviewComment(BaseModel):
    file_name: str
    review_comment: str
    requires_rework: bool
    suggested_improvements_markdown: str

class ReviewSummary(BaseModel):
    total_files_reviewed: int
    files_requiring_rework: int
    overall_assessment: str
    key_issues: List[str]
```

### 3. **Workflow-Based Architecture** 🔄

Built on Agent Framework's workflow system with two main executors:

- **ReviewSingleDiffExecutor**: Reviews all diffs in a loop
- **CompleteReviewExecutor**: Generates summary at the end

### 4. **Status Streaming** 📡

Uses shared state to stream review progress:

```python
await ctx.set_shared_state("current_status", f"Reviewing {file_name} ({idx}/{len(state.diffs)})")
```

## Comparison with Original agent.py

| Feature              | Original (LangGraph)                     | New (Agent Framework)          |
| -------------------- | ---------------------------------------- | ------------------------------ |
| **Graph Structure**  | Multi-node state machine                 | Linear workflow with executors |
| **Tools**            | Separate function defs                   | Integrated ReAct tools         |
| **Context Fetching** | Separate `fetch_additional_context` node | Built into agent tools         |
| **State Management** | TypedDict with annotations               | Pydantic BaseModel             |
| **Execution**        | Graph recursion with routing             | Sequential executor chain      |
| **Tool Calling**     | Manual prompting + JSON parsing          | Native agent tool support      |

## Usage

### Basic Usage

```python
from Agent_framework_agent import ReviewerHandler

async def review_pr():
    handler = ReviewerHandler(model_id="gemini-2.5-flash")

    result = await handler.run(
        repo_name="owner/repo",
        pr_number=123
    )

    # Access results
    print(f"Files reviewed: {result.summary.total_files_reviewed}")
    for review in result.review_comments:
        print(f"{review.file_name}: {review.review_comment}")
```

### Running Tests

```bash
# Interactive test
python test_agent_framework.py

# Choose option 1 for real PR (requires GIT_TOKEN)
# Choose option 2 for mock data testing
```

### Environment Variables

Required:

```bash
export GEMINI_API_KEY="your-gemini-api-key"
export GIT_TOKEN="your-github-token"  # For real PR reviews
```

Optional:

```bash
export MODEL_REVIEW_TIMEOUT_SECONDS=180
export MAX_PATCH_CHARS=20000
export MAX_CONTEXT_ROUNDS=3
```

## Implementation Details

### ReviewTools Class

Wraps async git operations for the agent:

```python
class ReviewTools:
    def __init__(self, git_service, repo_name, pr_number):
        self.git_service = git_service
        self.repo_name = repo_name
        self.pr_number = pr_number

    async def get_file_content(self, file_path: str) -> str:
        # Fetch file from PR branch
        ...

    def get_tools(self):
        # Returns sync wrappers for agent_framework
        ...
```

### Executor Pattern

Each executor inherits from `BaseModelExecutor` and implements a `@handler`:

```python
class ReviewSingleDiffExecutor(BaseModelExecutor):
    @handler
    async def handle(self, state: ReviewState, ctx: WorkflowContext[ReviewState]):
        # Main review logic
        for diff in state.diffs:
            # Run ReAct agent with tools
            result = await self.model.agent.run(
                review_prompt,
                response_format=ReviewComment
            )
            # Store in state
            review_comments.append(result)

        await ctx.send_message(state)
```

### Workflow Building

```python
workflow = (
    WorkflowBuilder()
    .set_start_executor(review_executor)
    .add_edge(review_executor, complete_executor)
    .build()
)

# Execute
async for event in workflow.run_stream(initial_state):
    if isinstance(event, WorkflowOutputEvent):
        result_state = event.data
```

## Key Differences from LangGraph Approach

### 1. Tool Integration

**LangGraph**: Manual JSON schema, parsing, and routing

```python
def _parse_model_json(self, raw_content: Any) -> Dict[str, Any] | None:
    # Manual parsing logic
    ...
```

**Agent Framework**: Native tool support

```python
tools = [get_file_content_sync, search_related_files_sync]
agent = ChatAgent(tools=tools)  # Tools automatically integrated
```

### 2. State Flow

**LangGraph**: Command-based routing with conditions

```python
async def review_single_diff(self, state: State) -> Command:
    if needs_context:
        return Command(goto="fetch_additional_context")
    else:
        return Command(goto="review_next")
```

**Agent Framework**: Linear workflow with executor chain

```python
workflow = (
    WorkflowBuilder()
    .set_start_executor(review_executor)  # Handles all diffs
    .add_edge(review_executor, complete_executor)
    .build()
)
```

### 3. Context Gathering

**LangGraph**: Separate node with MAX_CONTEXT_ROUNDS limit

```python
async def fetch_additional_context(self, state: State) -> Command:
    if state["context_round"] >= MAX_CONTEXT_ROUNDS:
        return Command(goto="complete_review")
    # Fetch files...
```

**Agent Framework**: Agent autonomously uses tools as needed

```python
# Agent decides when to call tools
result = await agent.run(prompt, response_format=ReviewComment)
# Tools are called transparently during execution
```

## Advantages

1. **Simpler Architecture**: Linear workflow vs complex state machine
2. **Native ReAct**: Built-in support for tool-calling patterns
3. **Type Safety**: Pydantic models throughout
4. **Less Boilerplate**: No manual JSON parsing, routing logic
5. **Better Observability**: Clear executor boundaries

## Trade-offs

1. **Less Dynamic**: LangGraph's conditional routing is more flexible
2. **Tool Overhead**: Each tool call may add latency
3. **Limited State Sharing**: Context rounds handled implicitly vs explicitly

## Future Enhancements

- [ ] Add parallel diff processing with fan-out/fan-in pattern
- [ ] Implement retry logic for tool failures
- [ ] Add caching for frequently requested files
- [ ] Create custom tools for specific review tasks (e.g., `check_tests`, `find_dependencies`)
- [ ] Add visualization with WorkflowViz
- [ ] Implement streaming output for real-time feedback

## Example Output

```
=== Review Summary ===
Total files: 5
Files needing rework: 2
Overall: The PR introduces solid improvements but has a few areas requiring attention

Key Issues:
  - Missing input validation in calculate() function
  - Inconsistent error handling in utils.py
  - Test coverage gaps for edge cases

=== Individual Reviews ===

File: src/example.py
Requires Rework: ⚠️  YES
Comment: Added input validation which is good, but should handle None explicitly
Suggestions:
  - Add docstring documenting the ValueError
  - Consider using typing.Union for type hints
  - Add unit tests for the validation logic
```

## Dependencies

```
agent-framework
pydantic
PyGithub
python-dotenv
```

## License

Same as parent project.
