"""Anthropic Claude adapter."""

from typing import Any

from consumer.llm_adapters.base import BaseLLMAdapter, LLMResponse, ToolCall


class AnthropicAdapter(BaseLLMAdapter):

    def __init__(self, api_key: str, model_name: str) -> None:
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model_name

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        # Convert MCP tool schemas → Anthropic tool format
        anthropic_tools = [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "input_schema": t.get("inputSchema") or {"type": "object", "properties": {}},
            }
            for t in tools
        ]

        # Split system message from conversation messages
        system_content = ""
        conversation: list[dict[str, Any]] = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                conversation.append(msg)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": conversation,
        }
        if system_content:
            kwargs["system"] = system_content
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        response = await self._client.messages.create(**kwargs)

        content_text: str | None = None
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                content_text = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        args=block.input or {},
                    )
                )

        return LLMResponse(content=content_text, tool_calls=tool_calls)
