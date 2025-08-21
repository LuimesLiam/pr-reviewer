from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import BaseMessage


class BaseLLM(ABC):
    def __init__(self, model: str, **kwargs):
        super().__init__()
        self.model = model

    @property
    @abstractmethod
    def _identifying_params(self) -> Dict[str, Any]:
        pass

    @property
    @abstractmethod
    def llm_type(self) -> str:
        pass

    @abstractmethod
    async def _call(self, prompt: ChatPromptTemplate, **kwargs) -> BaseMessage:
        """
        Main call for base string outputs. Subclasses implement this using their LLM client.
        """
        pass

    async def _invoke(self, prompt: ChatPromptTemplate, **kwargs) -> BaseMessage:
        """
        Unified, non-structured call. Subclasses usually don't need to override.
        """
        return await self._call(prompt, **kwargs)

    async def _invoke_structured_output(
        self, prompt: ChatPromptTemplate, schema: Optional[Dict] = None, **kwargs
    ) -> Any:
        """
        Unified structured call. Subclasses may override for custom model-specific logic.
        """
        # Default: try to get structured output as JSON
        response = await self._call(prompt, **kwargs)
        return response
