"""OpenRouter adapter — uses OpenRouter's OpenAI-compatible endpoint."""

from consumer.llm_adapters.openai_adapter import OpenAIAdapter

_OPEN_ROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterAdapter(OpenAIAdapter):

    def __init__(self, api_key: str, model_name: str) -> None:
        super().__init__(api_key=api_key, model_name=model_name, base_url=_OPEN_ROUTER_BASE_URL)
