"""OpenAI adapter (also works for compatible providers like Mistral, Cohere, Meta, OpenRouter)."""

import json
from typing import Any

from consumer.llm_adapters.base import BaseLLMAdapter, LLMResponse, ToolCall


class OpenAIAdapter(BaseLLMAdapter):

    def __init__(self, api_key: str, model_name: str, base_url: str | None = None) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model_name

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        # Convert MCP tool schemas → OpenAI function-calling format
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema") or {"type": "object", "properties": {}},
                },
            }
            for t in tools
        ]

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if openai_tools:
            kwargs["tools"] = openai_tools

        response = await self._client.chat.completions.create(**kwargs)

        if not response.choices:
            raise RuntimeError(
                f"Model '{self._model}' returned an empty choices array. "
                "The model may not support tool calling or rejected the request format."
            )

        choice = response.choices[0]
        msg = choice.message

        content_text: str | None = msg.content
        tool_calls: list[ToolCall] = []

        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        args=args,
                    )
                )

        return LLMResponse(content=content_text, tool_calls=tool_calls)
