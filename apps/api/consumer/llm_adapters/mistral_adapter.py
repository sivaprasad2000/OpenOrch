"""Mistral adapter — uses Mistral's OpenAI-compatible endpoint."""

from consumer.llm_adapters.openai_adapter import OpenAIAdapter

_MISTRAL_BASE_URL = "https://api.mistral.ai/v1"


class MistralAdapter(OpenAIAdapter):

    def __init__(self, api_key: str, model_name: str) -> None:
        super().__init__(api_key=api_key, model_name=model_name, base_url=_MISTRAL_BASE_URL)
