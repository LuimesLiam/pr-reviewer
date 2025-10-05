# pip install agent-framework openai
from pydantic import BaseModel
import os
import asyncio
from agent_framework import ChatAgent
from agent_framework.openai import OpenAIChatClient

chat_client = OpenAIChatClient(
    # names may vary slightly by version; these are the common ones
    api_key=os.environ["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    model_id="gemini-2.5-flash"    # e.g., gemini-1.5-pro / gemini-2.0-flash
)

agent = ChatAgent(
    chat_client=chat_client,
    name="HelpfulAssistant",
    instructions="You are a helpful assistant that extracts person information from text."
)

# Structured output works the same way as in the docs tutorial:


class PersonInfo(BaseModel):
    name: str | None = None
    age: int | None = None
    occupation: str | None = None


async def main():
    result = await agent.run(
        "John Smith is 35 and works as a software engineer.",
        response_format=PersonInfo
    )
    print(result)

asyncio.run(main())
