"""
Unified LLM client.

Usage
-----
    from shared.llm import create_llm_client, LLMProvider, Message

    client = create_llm_client(LLMProvider.ANTHROPIC, api_key="sk-ant-...")
    response = await client.complete(
        messages=[Message(role="user", content="Hello!")],
        model="claude-sonnet-4-6",
    )
    print(response.content)

Provider SDKs are imported lazily so you only need to install the package
for the provider(s) you actually use:
    - Anthropic → pip install anthropic
    - OpenAI    → pip install openai
"""

from abc import ABC, abstractmethod
from typing import Any

from shared.llm.types import LLMProvider, LLMResponse, Message


class LLMClient(ABC):
    """Abstract base class for all provider clients."""

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int = 1024,
        system: str | None = None,
        temperature: float = 1.0,
    ) -> LLMResponse:
        """
        Send a chat completion request.

        Parameters
        ----------
        messages:    Conversation history (user / assistant turns).
        model:       Provider-specific model identifier.
        max_tokens:  Maximum tokens to generate.
        system:      Optional system prompt (prepended before the conversation).
        temperature: Sampling temperature (0 = deterministic, higher = creative).
        """


# ── Anthropic ──────────────────────────────────────────────────────────────────


class AnthropicClient(LLMClient):
    """Client for Anthropic's Claude models."""

    def __init__(self, api_key: str) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "The 'anthropic' package is required to use the Anthropic provider. "
                "Install it with: pip install anthropic"
            ) from exc

        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int = 1024,
        system: str | None = None,
        temperature: float = 1.0,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if system:
            kwargs["system"] = system

        resp = await self._client.messages.create(**kwargs)

        return LLMResponse(
            content=resp.content[0].text,
            model=resp.model,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            raw=resp.model_dump(),
        )


# ── OpenAI ─────────────────────────────────────────────────────────────────────


class OpenAIClient(LLMClient):
    """Client for OpenAI's GPT models."""

    def __init__(self, api_key: str) -> None:
        try:
            import openai
        except ImportError as exc:
            raise ImportError(
                "The 'openai' package is required to use the OpenAI provider. "
                "Install it with: pip install openai"
            ) from exc

        self._client = openai.AsyncOpenAI(api_key=api_key)

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int = 1024,
        system: str | None = None,
        temperature: float = 1.0,
    ) -> LLMResponse:
        api_messages: list[dict[str, str]] = []
        if system:
            api_messages.append({"role": "system", "content": system})
        api_messages.extend({"role": m.role, "content": m.content} for m in messages)

        resp = await self._client.chat.completions.create(
            model=model,
            messages=api_messages,  # type: ignore[arg-type]
            max_tokens=max_tokens,
            temperature=temperature,
        )

        choice = resp.choices[0]
        usage = resp.usage

        return LLMResponse(
            content=choice.message.content or "",
            model=resp.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            raw=resp.model_dump(),
        )


# ── Factory ────────────────────────────────────────────────────────────────────

_PROVIDER_MAP: dict[LLMProvider, type[LLMClient]] = {
    LLMProvider.ANTHROPIC: AnthropicClient,
    LLMProvider.OPENAI: OpenAIClient,
}


def create_llm_client(provider: LLMProvider, api_key: str) -> LLMClient:
    """
    Instantiate the correct LLMClient for the given provider.

    Raises
    ------
    NotImplementedError
        If the provider has no client implementation yet.
    ImportError
        If the provider's SDK is not installed.
    """
    client_cls = _PROVIDER_MAP.get(provider)
    if client_cls is None:
        raise NotImplementedError(
            f"Provider '{provider.value}' does not have a client implementation yet. "
            f"Supported providers: {[p.value for p in _PROVIDER_MAP]}"
        )
    return client_cls(api_key)  # type: ignore[call-arg]
