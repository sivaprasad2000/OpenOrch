"""Unit tests for LLM adapter implementations.

All external SDK calls are mocked via sys.modules injection — no real API keys
or network access required, and the SDK packages do not need to be installed.
"""

import json
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from consumer.llm_adapters.anthropic_adapter import AnthropicAdapter
from consumer.llm_adapters.cohere_adapter import CohereAdapter
from consumer.llm_adapters.factory import create_adapter
from consumer.llm_adapters.google_adapter import GoogleAdapter
from consumer.llm_adapters.meta_adapter import MetaAdapter
from consumer.llm_adapters.mistral_adapter import MistralAdapter
from consumer.llm_adapters.open_router_adapter import OpenRouterAdapter
from consumer.llm_adapters.openai_adapter import OpenAIAdapter
from shared.llm.types import LLMProvider

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

SAMPLE_TOOLS = [
    {
        "name": "browser_click",
        "description": "Click an element in the browser",
        "inputSchema": {
            "type": "object",
            "properties": {"selector": {"type": "string"}},
            "required": ["selector"],
        },
    }
]

SAMPLE_MESSAGES = [
    {"role": "system", "content": "You are a browser automation agent."},
    {"role": "user", "content": "Click the submit button"},
]

USER_ONLY_MESSAGES = [
    {"role": "user", "content": "Click the submit button"},
]


# ---------------------------------------------------------------------------
# SDK mock factories
# ---------------------------------------------------------------------------

def _make_openai_sdk_mock() -> tuple[MagicMock, MagicMock]:
    """Return (sdk_module_mock, async_client_mock)."""
    mock_client = AsyncMock()
    mock_sdk = MagicMock()
    mock_sdk.AsyncOpenAI.return_value = mock_client
    return mock_sdk, mock_client


def _make_anthropic_sdk_mock() -> tuple[MagicMock, MagicMock]:
    """Return (sdk_module_mock, async_client_mock)."""
    mock_client = AsyncMock()
    mock_sdk = MagicMock()
    mock_sdk.AsyncAnthropic.return_value = mock_client
    return mock_sdk, mock_client


def _make_google_sdk_mock() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Return (genai_module_mock, types_module_mock, async_client_mock)."""
    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock()

    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client

    mock_types = MagicMock()
    # `from google.genai import types` resolves to mock_genai.types, so they
    # must be the same object for our assertions to work.
    mock_genai.types = mock_types

    return mock_genai, mock_types, mock_client


# ---------------------------------------------------------------------------
# Response builder helpers
# ---------------------------------------------------------------------------

# Anthropic

def _anthropic_text_block(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _anthropic_tool_block(
    tool_id: str = "toolu_01",
    name: str = "browser_click",
    input_data: dict[str, Any] | None = None,
) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = input_data or {"selector": "#submit"}
    return block


def _anthropic_response(*blocks: MagicMock) -> MagicMock:
    resp = MagicMock()
    resp.content = list(blocks)
    return resp


# OpenAI / OpenAI-compatible

def _openai_text_response(text: str) -> MagicMock:
    msg = MagicMock()
    msg.content = text
    msg.tool_calls = None
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _openai_tool_response(
    tool_id: str = "call_01",
    name: str = "browser_click",
    arguments: str = '{"selector": "#submit"}',
) -> MagicMock:
    tc = MagicMock()
    tc.id = tool_id
    tc.function.name = name
    tc.function.arguments = arguments
    msg = MagicMock()
    msg.content = None
    msg.tool_calls = [tc]
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _openai_multi_tool_response(calls: list[tuple[str, str, str]]) -> MagicMock:
    tool_calls = []
    for tool_id, name, arguments in calls:
        tc = MagicMock()
        tc.id = tool_id
        tc.function.name = name
        tc.function.arguments = arguments
        tool_calls.append(tc)
    msg = MagicMock()
    msg.content = None
    msg.tool_calls = tool_calls
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# Google

def _google_text_part(text: str) -> MagicMock:
    part = MagicMock()
    part.text = text
    part.function_call = None
    return part


def _google_tool_part(
    fc_id: str = "fc-1",
    name: str = "browser_click",
    args: dict[str, Any] | None = None,
) -> MagicMock:
    fc = MagicMock()
    fc.id = fc_id
    fc.name = name
    fc.args = args or {"selector": "#submit"}
    part = MagicMock()
    part.text = None
    part.function_call = fc
    return part


def _google_response(*parts: MagicMock) -> MagicMock:
    content = MagicMock()
    content.parts = list(parts)
    candidate = MagicMock()
    candidate.content = content
    resp = MagicMock()
    resp.candidates = [candidate]
    return resp


# ---------------------------------------------------------------------------
# AnthropicAdapter
# ---------------------------------------------------------------------------

class TestAnthropicAdapter:

    @pytest.fixture(autouse=True)
    def mock_sdk(self):
        mock_sdk, mock_client = _make_anthropic_sdk_mock()
        self.mock_sdk = mock_sdk
        self.mock_client = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            yield

    async def test_text_response(self):
        self.mock_client.messages.create = AsyncMock(
            return_value=_anthropic_response(_anthropic_text_block("Done"))
        )
        adapter = AnthropicAdapter(api_key="sk-test", model_name="claude-sonnet-4-6")
        result = await adapter.chat(messages=SAMPLE_MESSAGES, tools=[])

        assert result["content"] == "Done"
        assert result["tool_calls"] == []

    async def test_tool_call_response(self):
        self.mock_client.messages.create = AsyncMock(
            return_value=_anthropic_response(_anthropic_tool_block())
        )
        adapter = AnthropicAdapter(api_key="sk-test", model_name="claude-sonnet-4-6")
        result = await adapter.chat(messages=SAMPLE_MESSAGES, tools=SAMPLE_TOOLS)

        assert result["content"] is None
        assert len(result["tool_calls"]) == 1
        tc = result["tool_calls"][0]
        assert tc["id"] == "toolu_01"
        assert tc["name"] == "browser_click"
        assert tc["args"] == {"selector": "#submit"}

    async def test_mixed_text_and_tool_call(self):
        self.mock_client.messages.create = AsyncMock(
            return_value=_anthropic_response(
                _anthropic_text_block("Clicking now"),
                _anthropic_tool_block(),
            )
        )
        adapter = AnthropicAdapter(api_key="sk-test", model_name="claude-sonnet-4-6")
        result = await adapter.chat(messages=SAMPLE_MESSAGES, tools=SAMPLE_TOOLS)

        assert result["content"] == "Clicking now"
        assert len(result["tool_calls"]) == 1

    async def test_multiple_tool_calls(self):
        self.mock_client.messages.create = AsyncMock(
            return_value=_anthropic_response(
                _anthropic_tool_block("t1", "browser_click", {"selector": "#a"}),
                _anthropic_tool_block("t2", "browser_click", {"selector": "#b"}),
            )
        )
        adapter = AnthropicAdapter(api_key="sk-test", model_name="claude-sonnet-4-6")
        result = await adapter.chat(messages=SAMPLE_MESSAGES, tools=SAMPLE_TOOLS)

        assert len(result["tool_calls"]) == 2
        assert result["tool_calls"][0]["id"] == "t1"
        assert result["tool_calls"][1]["id"] == "t2"

    async def test_system_message_extracted(self):
        self.mock_client.messages.create = AsyncMock(
            return_value=_anthropic_response(_anthropic_text_block("ok"))
        )
        adapter = AnthropicAdapter(api_key="sk-test", model_name="claude-sonnet-4-6")
        await adapter.chat(messages=SAMPLE_MESSAGES, tools=[])

        call_kwargs = self.mock_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "You are a browser automation agent."
        for msg in call_kwargs["messages"]:
            assert msg["role"] != "system"

    async def test_no_system_message_omits_system_key(self):
        self.mock_client.messages.create = AsyncMock(
            return_value=_anthropic_response(_anthropic_text_block("ok"))
        )
        adapter = AnthropicAdapter(api_key="sk-test", model_name="claude-sonnet-4-6")
        await adapter.chat(messages=USER_ONLY_MESSAGES, tools=[])

        call_kwargs = self.mock_client.messages.create.call_args.kwargs
        assert "system" not in call_kwargs

    async def test_tools_converted_to_anthropic_format(self):
        self.mock_client.messages.create = AsyncMock(
            return_value=_anthropic_response(_anthropic_text_block("ok"))
        )
        adapter = AnthropicAdapter(api_key="sk-test", model_name="claude-sonnet-4-6")
        await adapter.chat(messages=USER_ONLY_MESSAGES, tools=SAMPLE_TOOLS)

        call_kwargs = self.mock_client.messages.create.call_args.kwargs
        anthropic_tools = call_kwargs["tools"]
        assert len(anthropic_tools) == 1
        assert anthropic_tools[0]["name"] == "browser_click"
        assert "input_schema" in anthropic_tools[0]

    async def test_no_tools_omits_tools_key(self):
        self.mock_client.messages.create = AsyncMock(
            return_value=_anthropic_response(_anthropic_text_block("ok"))
        )
        adapter = AnthropicAdapter(api_key="sk-test", model_name="claude-sonnet-4-6")
        await adapter.chat(messages=USER_ONLY_MESSAGES, tools=[])

        call_kwargs = self.mock_client.messages.create.call_args.kwargs
        assert "tools" not in call_kwargs


# ---------------------------------------------------------------------------
# OpenAIAdapter
# ---------------------------------------------------------------------------

class TestOpenAIAdapter:

    @pytest.fixture(autouse=True)
    def mock_sdk(self):
        mock_sdk, mock_client = _make_openai_sdk_mock()
        self.mock_sdk = mock_sdk
        self.mock_client = mock_client
        with patch.dict(sys.modules, {"openai": mock_sdk}):
            yield

    async def test_text_response(self):
        self.mock_client.chat.completions.create = AsyncMock(
            return_value=_openai_text_response("Done")
        )
        adapter = OpenAIAdapter(api_key="sk-test", model_name="gpt-4o")
        result = await adapter.chat(messages=USER_ONLY_MESSAGES, tools=[])

        assert result["content"] == "Done"
        assert result["tool_calls"] == []

    async def test_tool_call_response(self):
        self.mock_client.chat.completions.create = AsyncMock(
            return_value=_openai_tool_response()
        )
        adapter = OpenAIAdapter(api_key="sk-test", model_name="gpt-4o")
        result = await adapter.chat(messages=USER_ONLY_MESSAGES, tools=SAMPLE_TOOLS)

        assert result["content"] is None
        assert len(result["tool_calls"]) == 1
        tc = result["tool_calls"][0]
        assert tc["id"] == "call_01"
        assert tc["name"] == "browser_click"
        assert tc["args"] == {"selector": "#submit"}

    async def test_multiple_tool_calls(self):
        self.mock_client.chat.completions.create = AsyncMock(
            return_value=_openai_multi_tool_response([
                ("c1", "browser_click", '{"selector": "#a"}'),
                ("c2", "browser_click", '{"selector": "#b"}'),
            ])
        )
        adapter = OpenAIAdapter(api_key="sk-test", model_name="gpt-4o")
        result = await adapter.chat(messages=USER_ONLY_MESSAGES, tools=SAMPLE_TOOLS)

        assert len(result["tool_calls"]) == 2
        assert result["tool_calls"][0]["id"] == "c1"
        assert result["tool_calls"][1]["id"] == "c2"

    async def test_malformed_tool_args_fallback_to_empty_dict(self):
        self.mock_client.chat.completions.create = AsyncMock(
            return_value=_openai_tool_response(arguments="not-valid-json{{{")
        )
        adapter = OpenAIAdapter(api_key="sk-test", model_name="gpt-4o")
        result = await adapter.chat(messages=USER_ONLY_MESSAGES, tools=SAMPLE_TOOLS)

        assert result["tool_calls"][0]["args"] == {}

    async def test_tools_converted_to_openai_format(self):
        self.mock_client.chat.completions.create = AsyncMock(
            return_value=_openai_text_response("ok")
        )
        adapter = OpenAIAdapter(api_key="sk-test", model_name="gpt-4o")
        await adapter.chat(messages=USER_ONLY_MESSAGES, tools=SAMPLE_TOOLS)

        call_kwargs = self.mock_client.chat.completions.create.call_args.kwargs
        openai_tools = call_kwargs["tools"]
        assert openai_tools[0]["type"] == "function"
        assert openai_tools[0]["function"]["name"] == "browser_click"

    async def test_no_tools_omits_tools_key(self):
        self.mock_client.chat.completions.create = AsyncMock(
            return_value=_openai_text_response("ok")
        )
        adapter = OpenAIAdapter(api_key="sk-test", model_name="gpt-4o")
        await adapter.chat(messages=USER_ONLY_MESSAGES, tools=[])

        call_kwargs = self.mock_client.chat.completions.create.call_args.kwargs
        assert "tools" not in call_kwargs

    async def test_empty_choices_raises_runtime_error(self):
        resp = MagicMock()
        resp.choices = []
        self.mock_client.chat.completions.create = AsyncMock(return_value=resp)
        adapter = OpenAIAdapter(api_key="sk-test", model_name="some-model")
        with pytest.raises(RuntimeError, match="empty choices"):
            await adapter.chat(messages=USER_ONLY_MESSAGES, tools=[])

    async def test_none_choices_raises_runtime_error(self):
        resp = MagicMock()
        resp.choices = None
        self.mock_client.chat.completions.create = AsyncMock(return_value=resp)
        adapter = OpenAIAdapter(api_key="sk-test", model_name="some-model")
        with pytest.raises(RuntimeError, match="empty choices"):
            await adapter.chat(messages=USER_ONLY_MESSAGES, tools=[])

    def test_custom_base_url_passed_to_client(self):
        adapter = OpenAIAdapter(
            api_key="sk-test", model_name="gpt-4o", base_url="https://custom.ai/v1"
        )
        self.mock_sdk.AsyncOpenAI.assert_called_once_with(
            api_key="sk-test", base_url="https://custom.ai/v1"
        )


# ---------------------------------------------------------------------------
# GoogleAdapter
# ---------------------------------------------------------------------------

class TestGoogleAdapter:

    @pytest.fixture(autouse=True)
    def mock_sdk(self):
        mock_genai, mock_types, mock_client = _make_google_sdk_mock()
        self.mock_genai = mock_genai
        self.mock_types = mock_types
        self.mock_client = mock_client

        mock_google_ns = MagicMock()
        mock_google_ns.genai = mock_genai

        with patch.dict(sys.modules, {
            "google": mock_google_ns,
            "google.genai": mock_genai,
            "google.genai.types": mock_types,
        }):
            yield

    async def test_text_response(self):
        self.mock_client.aio.models.generate_content = AsyncMock(
            return_value=_google_response(_google_text_part("Done"))
        )
        adapter = GoogleAdapter(api_key="gk-test", model_name="gemini-2.0-flash")
        result = await adapter.chat(messages=SAMPLE_MESSAGES, tools=[])

        assert result["content"] == "Done"
        assert result["tool_calls"] == []

    async def test_tool_call_response(self):
        self.mock_client.aio.models.generate_content = AsyncMock(
            return_value=_google_response(_google_tool_part())
        )
        adapter = GoogleAdapter(api_key="gk-test", model_name="gemini-2.0-flash")
        result = await adapter.chat(messages=SAMPLE_MESSAGES, tools=SAMPLE_TOOLS)

        assert result["content"] is None
        assert len(result["tool_calls"]) == 1
        tc = result["tool_calls"][0]
        assert tc["name"] == "browser_click"
        assert tc["args"] == {"selector": "#submit"}

    async def test_multiple_tool_calls(self):
        self.mock_client.aio.models.generate_content = AsyncMock(
            return_value=_google_response(
                _google_tool_part("fc-1", "browser_click", {"selector": "#a"}),
                _google_tool_part("fc-2", "browser_click", {"selector": "#b"}),
            )
        )
        adapter = GoogleAdapter(api_key="gk-test", model_name="gemini-2.0-flash")
        result = await adapter.chat(messages=SAMPLE_MESSAGES, tools=SAMPLE_TOOLS)

        assert len(result["tool_calls"]) == 2

    async def test_system_message_extracted_to_config(self):
        self.mock_client.aio.models.generate_content = AsyncMock(
            return_value=_google_response(_google_text_part("ok"))
        )
        adapter = GoogleAdapter(api_key="gk-test", model_name="gemini-2.0-flash")
        await adapter.chat(messages=SAMPLE_MESSAGES, tools=[])

        # Inspect what kwargs were passed to GenerateContentConfig(...)
        config_call_kwargs = self.mock_types.GenerateContentConfig.call_args.kwargs
        assert config_call_kwargs["system_instruction"] == "You are a browser automation agent."

    async def test_assistant_role_mapped_to_model(self):
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
            {"role": "user", "content": "Click submit"},
        ]
        self.mock_client.aio.models.generate_content = AsyncMock(
            return_value=_google_response(_google_text_part("ok"))
        )
        adapter = GoogleAdapter(api_key="gk-test", model_name="gemini-2.0-flash")
        await adapter.chat(messages=messages, tools=[])

        # Inspect what kwargs were passed to each types.Content(...) call
        content_calls = self.mock_types.Content.call_args_list
        roles = [call.kwargs["role"] for call in content_calls]
        assert roles == ["user", "model", "user"]

    async def test_tool_call_id_falls_back_to_name_when_absent(self):
        fc = MagicMock()
        fc.id = None
        fc.name = "browser_click"
        fc.args = {"selector": "#btn"}
        part = MagicMock()
        part.text = None
        part.function_call = fc
        self.mock_client.aio.models.generate_content = AsyncMock(
            return_value=_google_response(part)
        )
        adapter = GoogleAdapter(api_key="gk-test", model_name="gemini-2.0-flash")
        result = await adapter.chat(messages=USER_ONLY_MESSAGES, tools=SAMPLE_TOOLS)

        assert result["tool_calls"][0]["id"] == "browser_click"

    async def test_no_tools_passes_none_config(self):
        self.mock_client.aio.models.generate_content = AsyncMock(
            return_value=_google_response(_google_text_part("ok"))
        )
        adapter = GoogleAdapter(api_key="gk-test", model_name="gemini-2.0-flash")
        await adapter.chat(messages=USER_ONLY_MESSAGES, tools=[])

        call_kwargs = self.mock_client.aio.models.generate_content.call_args.kwargs
        assert call_kwargs["config"] is None


# ---------------------------------------------------------------------------
# OpenAI-compatible wrapper adapters (Mistral, Cohere, Meta, OpenRouter)
# ---------------------------------------------------------------------------

_COMPATIBLE_ADAPTERS = [
    (MistralAdapter,    "https://api.mistral.ai/v1"),
    (CohereAdapter,     "https://api.cohere.com/compatibility/v1"),
    (MetaAdapter,       "https://api.llama.com/v1"),
    (OpenRouterAdapter, "https://openrouter.ai/api/v1"),
]


@pytest.mark.parametrize("adapter_cls,expected_base_url", _COMPATIBLE_ADAPTERS)
def test_compatible_adapter_uses_correct_base_url(adapter_cls, expected_base_url):
    mock_sdk, _ = _make_openai_sdk_mock()
    with patch.dict(sys.modules, {"openai": mock_sdk}):
        adapter_cls(api_key="sk-test", model_name="some-model")
    _, kwargs = mock_sdk.AsyncOpenAI.call_args
    assert kwargs.get("base_url") == expected_base_url


@pytest.mark.parametrize("adapter_cls,_", _COMPATIBLE_ADAPTERS)
async def test_compatible_adapter_text_response(adapter_cls, _):
    mock_sdk, mock_client = _make_openai_sdk_mock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_openai_text_response("Task complete")
    )
    with patch.dict(sys.modules, {"openai": mock_sdk}):
        adapter = adapter_cls(api_key="sk-test", model_name="some-model")
        result = await adapter.chat(messages=USER_ONLY_MESSAGES, tools=[])

    assert result["content"] == "Task complete"
    assert result["tool_calls"] == []


@pytest.mark.parametrize("adapter_cls,_", _COMPATIBLE_ADAPTERS)
async def test_compatible_adapter_tool_call(adapter_cls, _):
    mock_sdk, mock_client = _make_openai_sdk_mock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_openai_tool_response(
            tool_id="call_x",
            name="browser_click",
            arguments=json.dumps({"selector": "#go"}),
        )
    )
    with patch.dict(sys.modules, {"openai": mock_sdk}):
        adapter = adapter_cls(api_key="sk-test", model_name="some-model")
        result = await adapter.chat(messages=USER_ONLY_MESSAGES, tools=SAMPLE_TOOLS)

    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["args"] == {"selector": "#go"}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestFactory:

    def _openai_ctx(self):
        mock_sdk, _ = _make_openai_sdk_mock()
        return patch.dict(sys.modules, {"openai": mock_sdk})

    def _anthropic_ctx(self):
        mock_sdk, _ = _make_anthropic_sdk_mock()
        return patch.dict(sys.modules, {"anthropic": mock_sdk})

    def _google_ctx(self):
        mock_genai, mock_types, _ = _make_google_sdk_mock()
        mock_google_ns = MagicMock()
        mock_google_ns.genai = mock_genai
        return patch.dict(sys.modules, {
            "google": mock_google_ns,
            "google.genai": mock_genai,
            "google.genai.types": mock_types,
        })

    def test_anthropic_returns_anthropic_adapter(self):
        with self._anthropic_ctx():
            adapter = create_adapter(LLMProvider.ANTHROPIC, "sk-test", "claude-sonnet-4-6")
        assert isinstance(adapter, AnthropicAdapter)

    def test_openai_returns_openai_adapter(self):
        with self._openai_ctx():
            adapter = create_adapter(LLMProvider.OPENAI, "sk-test", "gpt-4o")
        assert isinstance(adapter, OpenAIAdapter)

    def test_google_returns_google_adapter(self):
        with self._google_ctx():
            adapter = create_adapter(LLMProvider.GOOGLE, "gk-test", "gemini-2.0-flash")
        assert isinstance(adapter, GoogleAdapter)

    def test_mistral_returns_mistral_adapter(self):
        with self._openai_ctx():
            adapter = create_adapter(LLMProvider.MISTRAL, "sk-test", "mistral-large-latest")
        assert isinstance(adapter, MistralAdapter)

    def test_cohere_returns_cohere_adapter(self):
        with self._openai_ctx():
            adapter = create_adapter(LLMProvider.COHERE, "sk-test", "command-r-plus")
        assert isinstance(adapter, CohereAdapter)

    def test_meta_returns_meta_adapter(self):
        with self._openai_ctx():
            adapter = create_adapter(LLMProvider.META, "sk-test", "Llama-4-Scout-17B-16E-Instruct")
        assert isinstance(adapter, MetaAdapter)

    def test_open_router_returns_open_router_adapter(self):
        with self._openai_ctx():
            adapter = create_adapter(LLMProvider.OPEN_ROUTER, "sk-test", "openai/gpt-4o")
        assert isinstance(adapter, OpenRouterAdapter)

    def test_all_enum_providers_are_supported(self):
        """Every value in the LLMProvider enum must be handled by the factory."""
        for provider in LLMProvider:
            ctx: Any
            if provider == LLMProvider.ANTHROPIC:
                ctx = self._anthropic_ctx()
            elif provider == LLMProvider.GOOGLE:
                ctx = self._google_ctx()
            else:
                ctx = self._openai_ctx()

            with ctx:
                create_adapter(provider, "sk-test", "model-x")
