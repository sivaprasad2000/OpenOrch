"""Meta Llama adapter — uses Meta's OpenAI-compatible Llama API."""

from consumer.llm_adapters.openai_adapter import OpenAIAdapter

_META_BASE_URL = "https://api.llama.com/v1"


class MetaAdapter(OpenAIAdapter):

    def __init__(self, api_key: str, model_name: str) -> None:
        super().__init__(api_key=api_key, model_name=model_name, base_url=_META_BASE_URL)
