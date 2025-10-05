import asyncio
from pydantic import BaseModel
from agent_framework import ChatAgent
from agent_framework.openai import OpenAIChatClient
import os
# Define tools (regular Python functions)


def lookup_age(name: str) -> int:
    # ...call your DB or service...
    return 35


def lookup_job(name: str) -> str:
    return "software engineer"


tools = [lookup_age, lookup_job]

# Chat client (swap in Azure/OpenAI/Gemini-compat as you wish)
chat_client = OpenAIChatClient(
    # names may vary slightly by version; these are the common ones
    api_key=os.environ["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    model_id="gemini-2.5-flash"    # e.g., gemini-1.5-pro / gemini-2.0-flash
)
agent = ChatAgent(
    chat_client=chat_client,
    name="ReActExtractor",
    instructions=(
        "You are a ReAct agent. Think step-by-step, call tools as needed to fact-check, "
        "and finally produce the requested structured output."
    ),
    tools=tools,  # ← enables function tools
)


class PersonInfo(BaseModel):
    name: str | None = None
    age: int | None = None
    occupation: str | None = None


async def main():
    result = await agent.run(
        "Extract info for John Smith (use tools if necessary).",
        response_format=PersonInfo,  # ← final structured output
    )
    print(result.value)  # PersonInfo(...)

asyncio.run(main())
