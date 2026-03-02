"""Google Gemini adapter using the google-genai SDK."""

from typing import Any

from consumer.llm_adapters.base import BaseLLMAdapter, LLMResponse, ToolCall


class GoogleAdapter(BaseLLMAdapter):

    def __init__(self, api_key: str, model_name: str) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model_name

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        from google.genai import types

        # Split system message out; Google treats it as system_instruction
        system_text: str | None = None
        conversation: list[dict[str, Any]] = []
        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            else:
                conversation.append(msg)

        # Convert to google.genai Content objects
        contents = [
            types.Content(
                role="user" if m["role"] == "user" else "model",
                parts=[types.Part(text=m["content"])],
            )
            for m in conversation
        ]

        # Convert MCP tool schemas → FunctionDeclaration format
        fn_decls = [
            types.FunctionDeclaration(
                name=t["name"],
                description=t.get("description", ""),
                parameters=t.get("inputSchema") or {"type": "object", "properties": {}},
            )
            for t in tools
        ]

        config_kwargs: dict[str, Any] = {}
        if system_text:
            config_kwargs["system_instruction"] = system_text
        if fn_decls:
            config_kwargs["tools"] = [types.Tool(function_declarations=fn_decls)]

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(**config_kwargs) if config_kwargs else None,
        )

        content_text: str | None = None
        tool_calls: list[ToolCall] = []

        for part in response.candidates[0].content.parts:
            if part.function_call is not None:
                fc = part.function_call
                tool_calls.append(
                    ToolCall(
                        id=getattr(fc, "id", None) or fc.name,
                        name=fc.name,
                        args=dict(fc.args) if fc.args else {},
                    )
                )
            elif part.text:
                content_text = part.text

        return LLMResponse(content=content_text, tool_calls=tool_calls)
