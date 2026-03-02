"""Factory for creating LLM adapters by provider."""

from consumer.llm_adapters.base import BaseLLMAdapter
from shared.llm.types import LLMProvider


def create_adapter(provider: LLMProvider, api_key: str, model_name: str) -> BaseLLMAdapter:
    """Return the correct adapter for the given provider.

    Args:
        provider:   LLMProvider enum value.
        api_key:    Provider API key.
        model_name: Model identifier (e.g. "claude-sonnet-4-6", "gpt-4o").

    Raises:
        ValueError: If the provider is not supported.
    """

    if provider == LLMProvider.ANTHROPIC:
        from consumer.llm_adapters.anthropic_adapter import AnthropicAdapter
        return AnthropicAdapter(api_key=api_key, model_name=model_name)

    if provider == LLMProvider.OPENAI:
        from consumer.llm_adapters.openai_adapter import OpenAIAdapter
        return OpenAIAdapter(api_key=api_key, model_name=model_name)

    if provider == LLMProvider.GOOGLE:
        from consumer.llm_adapters.google_adapter import GoogleAdapter
        return GoogleAdapter(api_key=api_key, model_name=model_name)

    if provider == LLMProvider.MISTRAL:
        from consumer.llm_adapters.mistral_adapter import MistralAdapter
        return MistralAdapter(api_key=api_key, model_name=model_name)

    if provider == LLMProvider.COHERE:
        from consumer.llm_adapters.cohere_adapter import CohereAdapter
        return CohereAdapter(api_key=api_key, model_name=model_name)

    if provider == LLMProvider.META:
        from consumer.llm_adapters.meta_adapter import MetaAdapter
        return MetaAdapter(api_key=api_key, model_name=model_name)

    if provider == LLMProvider.OPEN_ROUTER:
        from consumer.llm_adapters.open_router_adapter import OpenRouterAdapter
        return OpenRouterAdapter(api_key=api_key, model_name=model_name)

    raise ValueError(f"Unsupported LLM provider: {provider!r}")  # pragma: no cover
