from typing import Annotated
from pydantic import Field

from pydantic import BaseModel
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import AzureCliCredential
from agent_framework.openai import OpenAIChatClient
import asyncio
from agent_framework import ChatAgent
import os

from agent_framework import AgentRunResponse

from typing import Annotated
from pydantic import Field
from agent_framework import ai_function


@ai_function(name="weather_tool", description="Retrieves weather information for any location")
def get_weather(
    location: Annotated[str, Field(description="The location to get the weather for.")],
) -> str:
    return f"The weather in {location} is cloudy with a high of 15°C."


chat_client = OpenAIChatClient(
    # names may vary slightly by version; these are the common ones
    api_key=os.environ["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    model_id="gemini-2.5-flash"
)


agent = ChatAgent(
    chat_client=chat_client,
    name="HelpfulAssistant",
    instructions="You are a helpful assistant that extracts person information from text.",
    tools=[get_weather]
)


async def main():
    result = await agent.run("What is the weather like in Amsterdam?")
    print(result.text)

asyncio.run(main())
