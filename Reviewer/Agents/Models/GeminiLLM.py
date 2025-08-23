import os
import json
import asyncio
from typing import Any, Dict, Optional
from pydantic import SecretStr
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage

from Agents.Models.BaseLLM import BaseLLM


class GeminiLLM(BaseLLM):
    def __init__(self, model: str = "gemini-2.5-flash"):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.temperature = 0.7
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set")

        self.model = model
        # Fix for Pydantic v2: ensure model is rebuilt
        ChatGoogleGenerativeAI.model_rebuild()
        self.llm = ChatGoogleGenerativeAI(
            api_key=SecretStr(self.api_key),
            model=self.model,
            temperature=self.temperature,
        )

    @property
    def _identifying_params(self):
        return {"model": self.model}

    @property
    def llm_type(self):
        return "gemini"

    async def _call(self, prompt: ChatPromptTemplate, **kwargs) -> BaseMessage:
        chain = prompt | self.llm
        response = await chain.ainvoke({"input": prompt})
        return response

    async def _invoke_structured_output(
        self,
        prompt: ChatPromptTemplate,
        schema: Dict,
        **kwargs,
    ) -> Any:
        # Choose schema (default to the one defined)
        try:
            structured_llm = self.llm.with_structured_output(
                schema=schema,
                # method="function_calling",
            )
            chain = prompt | structured_llm
            response = await chain.ainvoke({"input": prompt})
        except Exception as e:
            raise e
        return response


# Example usage


async def main():
    # Initialize your structured Gemini LLM
    llm = GeminiLLM(model="gemini-2.5-flash")

    # Prepare a simple chat prompt
    system_message = "You are an analytics assistant that summarizes user asks."
    user_message = "I want to analyze customer churn rates for Q2 and visualize new charts."
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("user", user_message),
    ])

    json_schema: Dict = {
        "title": "CompleteAsk",
        "description": "A statement describing the complete analytics ask from the user.",
        "type": "object",
        "properties": {
                "ask": {
                    "type": "string",
                    "description": "A natural language statement describing the complete analytics ask from the user.",
                },
            "followup": {
                    "type": "boolean",
                    "description": "True if the question was a follow-up, false otherwise.",
                },
            "visualize": {
                    "type": "string",
                    "description": (
                        "Indicator of when and if the user wants to see a visualization of the answer. "
                        "'previous', 'new', or 'no'."
                    ),
                },
        },
        "required": ["ask", "followup", "visualize"],
    }

    # Invoke structured output
    structured = await llm._invoke_structured_output(prompt, schema=json_schema)
    print(json.dumps(structured, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
