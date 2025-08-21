from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict
from typing import Literal, Sequence, List, Dict, Any
from langchain_core.messages import BaseMessage, HumanMessage, RemoveMessage, AIMessage
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
