from pydantic import BaseModel
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import AzureCliCredential
from agent_framework.openai import OpenAIChatClient
import asyncio
from agent_framework import ChatAgent
import os

from agent_framework import AgentRunResponse


class PersonInfo(BaseModel):
    """Information about a person."""
    name: str | None = None
    age: int | None = None
    occupation: str | None = None


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


async def main():
    result = await agent.run(
        "John Smith is 35 and works as a software engineer.",
        response_format=PersonInfo
    )
    print(result)

asyncio.run(main())


async def main2():
    query = "Alice is 30 years old and works as a data scientist."
    final_response = await AgentRunResponse.from_agent_response_generator(
        agent.run_stream(query, response_format=PersonInfo),
        output_format_type=PersonInfo,
    )

    if final_response.value:
        person_info = final_response.value
        # type: ignore
        print(
            f"Name: {person_info.name}, Age: {person_info.age}, Occupation: {person_info.occupation}")

asyncio.run(main2())
