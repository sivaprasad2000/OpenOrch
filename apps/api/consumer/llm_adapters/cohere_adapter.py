"""Cohere adapter — uses Cohere's OpenAI-compatible endpoint."""

from consumer.llm_adapters.openai_adapter import OpenAIAdapter

_COHERE_BASE_URL = "https://api.cohere.com/compatibility/v1"


class CohereAdapter(OpenAIAdapter):

    def __init__(self, api_key: str, model_name: str) -> None:
        super().__init__(api_key=api_key, model_name=model_name, base_url=_COHERE_BASE_URL)
