# LangGraph vs Agent Framework: Implementation Comparison

This document compares the original LangGraph-based reviewer with the new Agent Framework implementation.

## High-Level Architecture

### LangGraph Approach (Original)

```
┌─────────────┐
│   START     │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│  fetch_diffs        │ ← Loads PR diffs
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ review_single_diff  │ ← Reviews ONE diff at a time
└──────┬──────────────┘
       │
       ├──→ mode='request_context'? ──→ fetch_additional_context ──┐
       │                                         │                  │
       │                                         ▼                  │
       │                                    [Increment round]       │
       │                                         │                  │
       │                                         ▼                  │
       │                                    round < MAX? ───────────┘
       │                                         │
       │                                         ▼ No
       ▼ mode='feedback'                         │
       │                                         │
       ├─────────────────────────────────────────┘
       │
       ▼ All diffs done?
       │
       ▼
┌─────────────────────┐
│  complete_review    │ ← Finalizes and outputs
└──────┬──────────────┘
       │
       ▼
     [END]
```

### Agent Framework Approach (New)

```
┌─────────────┐
│   START     │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────┐
│ ReviewSingleDiffExecutor     │
│ ┌──────────────────────────┐ │
│ │ For each diff:           │ │
│ │  - Run ReAct Agent       │ │
│ │  - Agent has tools:      │ │
│ │    * get_file_content    │ │
│ │    * search_related_files│ │
│ │  - Agent decides when    │ │
│ │    to use tools          │ │
│ │  - Store review          │ │
│ │  - Stream status         │ │
│ └──────────────────────────┘ │
└──────┬───────────────────────┘
       │
       ▼
┌──────────────────────────────┐
│ CompleteReviewExecutor       │
│  - Summarize all reviews     │
│  - Generate structured output│
└──────┬───────────────────────┘
       │
       ▼
     [END]
```

## Code Complexity Comparison

### 1. Tool/Function Calling

#### LangGraph

````python
# Manual JSON schema definition
json_schema = {
  "mode": "request_context",
  "file_name": string,
  "reason": string,
  "requested_files": [string, ...]
}

# Manual parsing
def _parse_model_json(self, raw_content: Any) -> Dict[str, Any] | None:
    if isinstance(raw_content, str):
        # Try to find JSON block
        if "```json" in raw_content:
            start = raw_content.find("```json") + 7
            end = raw_content.find("```", start)
            raw_content = raw_content[start:end].strip()
        try:
            parsed = json.loads(raw_content)
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return None
    # ... more parsing logic

# Manual routing based on mode
if parsed.get("mode") == "request_context":
    return Command(goto="fetch_additional_context", update=new_state)
elif parsed.get("mode") == "feedback":
    return Command(goto="review_next", update=new_state)
````

#### Agent Framework

```python
# Native tool functions
def get_file_content(file_path: str) -> str:
    """Fetch the full content of a file from the PR branch."""
    # Implementation
    return content

def search_related_files(search_term: str) -> str:
    """Search for files related to a given term."""
    # Implementation
    return matches

# Tools automatically integrated
tools = [get_file_content, search_related_files]
agent = ChatAgent(
    chat_client=chat_client,
    name="CodeReviewer",
    instructions=instructions,
    tools=tools  # ← That's it!
)

# Agent decides when to call tools transparently
result = await agent.run(prompt, response_format=ReviewComment)
# Agent handles tool calling internally
```

**Reduction**: ~50 lines of manual JSON parsing → 0 lines

### 2. State Management

#### LangGraph

```python
# TypedDict with manual annotations
from typing_extensions import Annotated, TypedDict

class State(TypedDict):
    event_queue: Annotated[asyncio.Queue[str], "Queue for streaming"]
    repo_name: str
    pr_number: int
    review_comments: List[ReviewComment]
    diffs: List[Dict[str, Any]]
    current_diff_index: int  # Manual tracking
    additional_context: Dict[str, str]
    pending_context_request: List[str]
    context_round: int  # Manual round counting
    # ... more fields

# Manual state updates
state["current_diff_index"] += 1
state["context_round"] += 1
state["additional_context"].update(new_context)
```

#### Agent Framework

```python
# Pydantic model with validation
class ReviewState(BaseModel):
    repo_name: str
    pr_number: int
    diffs: List[Dict[str, Any]] = []
    review_comments: List[ReviewComment] = []
    summary: ReviewSummary | None = None
    # No need for index/round tracking

# State flows naturally through executors
async def handle(self, state: ReviewState, ctx: WorkflowContext[ReviewState]):
    # Simple loop, no manual tracking
    for diff in state.diffs:
        review = await self.model.agent.run(...)
        state.review_comments.append(review)

    await ctx.send_message(state)
```

**Reduction**: 9 state fields → 5 state fields (44% reduction)

### 3. Context Gathering Logic

#### LangGraph

```python
async def review_single_diff(self, state: State) -> Command:
    # Get current diff
    idx = state.get("current_diff_index", 0)
    diff = state["diffs"][idx]

    # Call model
    response = await self.model._call(prompt, ...)
    parsed = self._parse_model_json(response.content)

    # Check mode
    if parsed.get("mode") == "request_context":
        new_state = {
            "pending_context_request": parsed.get("requested_files", []),
            "context_round": state.get("context_round", 0)
        }
        return Command(goto="fetch_additional_context", update=new_state)
    # ... handle feedback mode

async def fetch_additional_context(self, state: State) -> Command:
    # Check round limit
    round_num = state.get("context_round", 0)
    if round_num >= MAX_CONTEXT_ROUNDS:
        logger.warning("Max context rounds reached")
        return Command(goto="complete_review")

    # Fetch files
    requested = state.get("pending_context_request", [])
    new_context = {}
    for file_path in requested:
        candidates = await self.git_service.find_file_in_pr(...)
        if candidates:
            content = await self.git_service.get_file_from_pull_request(...)
            new_context[candidates[0]] = content

    # Update state
    new_state = {
        "additional_context": {**state.get("additional_context", {}), **new_context},
        "context_round": round_num + 1,
        "pending_context_request": []
    }
    return Command(goto="review_single_diff", update=new_state)
```

#### Agent Framework

```python
# Tools are available, agent uses them as needed
class ReviewTools:
    async def get_file_content(self, file_path: str) -> str:
        result = await self.git_service.get_file_from_pull_request(...)
        return result.get("decoded_content", "File not found")

# Agent calls tools during reasoning (no manual routing)
async def handle(self, state: ReviewState, ctx: WorkflowContext[ReviewState]):
    for diff in state.diffs:
        # Agent autonomously decides if/when to call tools
        result = await self.model.agent.run(
            review_prompt,
            response_format=ReviewComment
        )
        state.review_comments.append(result.value)

    await ctx.send_message(state)
```

**Reduction**: ~80 lines of routing logic → ~10 lines

### 4. Graph/Workflow Construction

#### LangGraph

```python
# Build state graph with multiple nodes and conditional edges
builder = StateGraph(State)

# Add nodes
builder.add_node("fetch_diffs", self.fetch_diffs)
builder.add_node("review_single_diff", self.review_single_diff)
builder.add_node("fetch_additional_context", self.fetch_additional_context)
builder.add_node("complete_review", self.complete_review)

# Add edges
builder.add_edge(START, "fetch_diffs")
builder.add_edge("fetch_diffs", "review_single_diff")

# Conditional routing in each node via Command(goto=...)
# review_single_diff decides next node based on mode
# fetch_additional_context decides based on round count

builder.add_edge("complete_review", END)
graph = builder.compile()
```

#### Agent Framework

```python
# Simple linear workflow
workflow = (
    WorkflowBuilder()
    .set_start_executor(review_executor)
    .add_edge(review_executor, complete_executor)
    .build()
)
```

**Reduction**: ~15 lines → 5 lines (67% reduction)

## Performance Characteristics

| Metric              | LangGraph                     | Agent Framework               |
| ------------------- | ----------------------------- | ----------------------------- |
| **Lines of Code**   | ~800                          | ~350                          |
| **Graph Nodes**     | 4 nodes + conditional routing | 2 executors                   |
| **State Fields**    | 9+ fields                     | 5 fields                      |
| **Manual Parsing**  | Yes (JSON extraction)         | No (native structured output) |
| **Context Rounds**  | Explicit (MAX_CONTEXT_ROUNDS) | Implicit (agent decides)      |
| **Tool Calling**    | Manual via JSON               | Native via ReAct              |
| **Type Safety**     | Partial (TypedDict)           | Full (Pydantic)               |
| **Execution Model** | Recursive graph traversal     | Sequential executor chain     |

## When to Use Each

### Use LangGraph When:

- ✅ You need complex conditional routing
- ✅ Multiple parallel paths are required
- ✅ Fine-grained control over state transitions
- ✅ Explicit limits on retries/rounds are critical
- ✅ Existing LangGraph ecosystem/tools

### Use Agent Framework When:

- ✅ ReAct pattern fits your use case
- ✅ Prefer declarative tool definitions
- ✅ Want native structured output support
- ✅ Linear or simple fan-out/fan-in workflows
- ✅ Working within Microsoft ecosystem

## Migration Path

If migrating from LangGraph to Agent Framework:

1. **Identify nodes** → Convert to Executors

   - Each node becomes an Executor class
   - `@handler` method replaces node function

2. **Extract tool logic** → Define tool functions

   - Manual JSON parsing → Native tool functions
   - Context fetching → Tool methods

3. **Simplify state** → Use Pydantic models

   - Remove routing fields (mode, round, index)
   - Keep only data fields

4. **Flatten graph** → Build linear workflow

   - Remove conditional edges
   - Let agent handle decisions via tools

5. **Test incrementally** → Verify behavior
   - Start with mock data
   - Compare outputs with original

## Conclusion

**Agent Framework** reduces code complexity by ~50% for this use case by:

- Eliminating manual JSON parsing and routing
- Leveraging native ReAct tool calling
- Simplifying state management with Pydantic
- Using a linear workflow model

**Trade-off**: Less flexibility in complex routing scenarios, but simpler and more maintainable for the common case of "review → gather context → summarize."
