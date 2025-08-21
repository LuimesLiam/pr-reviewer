from .BaseLLM import BaseLLM
from .GeminiLLM import GeminiLLM


def llm_factory(model_name: str) -> BaseLLM:
    """
    Factory function to create an instance of the appropriate LLM class based on the model name.
    """
    if model_name == "gemini":
        return GeminiLLM()
    else:
        raise ValueError(f"Unsupported model name: {model_name}")
