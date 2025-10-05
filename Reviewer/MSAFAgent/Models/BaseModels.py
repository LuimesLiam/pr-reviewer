import asyncio
from agent_framework.openai import OpenAIChatClient
import os
from agent_framework import ChatAgent
from agent_framework import Executor
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import AzureCliCredential


# class Model:
#     def __init__(self, agent_name: str, instructions: str, model_id: str = "gemini-2.5-flash"):
#         self.chat_client = OpenAIChatClient(
#             api_key=os.environ["GEMINI_API_KEY"],
#             base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
#             model_id=model_id
#         )
#         self.agent = ChatAgent(
#             chat_client=self.chat_client,
#             name=agent_name,
#             instructions=instructions
#         )


class Model:
    def __init__(self, agent_name: str, instructions: str, model_id: str = "gpt-5-mini"):
        self.chat_client = OpenAIChatClient(
            api_key=os.environ["OPENAI_API_KEY"],
            model_id=model_id
        )

        self.agent = self.chat_client.create_agent(
            instructions=instructions,
            name=agent_name
        )


class BaseModelExecutor(Executor):
    """Base executor that initializes and shares the model instance."""

    def __init__(self, id: str, model: Model):
        super().__init__(id=id)
        self.model = model


# async def main():
#     agent = Model("Joker", "You are good at telling jokes.")
#     result = await agent.agent.run("Tell me a joke about a pirate.")
#     print(result.text)

# asyncio.run(main())
