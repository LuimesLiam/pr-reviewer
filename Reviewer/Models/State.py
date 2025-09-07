from typing_extensions import Annotated, TypedDict
from typing import Sequence, List, Dict, Any
from langchain_core.messages import BaseMessage
import asyncio


class ReviewComment(TypedDict):
    file_name: str
    review_comment: str
    requires_rework: bool
    suggested_improvements_markdown: str


class State(TypedDict):
    # messages: Annotated[Sequence[BaseMessage], add_messages]
    # input: str
    # ai_generated_ask: str
    event_queue: Annotated[asyncio.Queue[str], "Queue for streaming updates"]
    repo_name: str
    pr_number: int
    review_comments: List[ReviewComment]
    grouped_files: Dict[Dict, Any]
    messages: Sequence[BaseMessage]
    diffs: List[Dict[str, Any]]
    current_diff_index: int
    additional_context: Dict[str, str]
    pending_context_request: List[str]
    context_round: int
