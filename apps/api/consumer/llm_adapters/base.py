"""Abstract base for LLM provider adapters."""

from abc import ABC, abstractmethod
from typing import Any, TypedDict


class ToolCall(TypedDict):
    id: str
    name: str
    args: dict[str, Any]


class LLMResponse(TypedDict):
    content: str | None
    tool_calls: list[ToolCall]


class BaseLLMAdapter(ABC):

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """Send messages to the LLM and return the response.

        Args:
            messages: Conversation history in OpenAI-style format.
            tools:    MCP tool schemas (as returned by tools/list).

        Returns:
            LLMResponse with optional text content and a list of tool calls.
        """
        ...
