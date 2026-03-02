"""Tests for consumer/agent.py — the LLM-driven step executor.

Covers pre-flight snapshot injection, normal completion, snapshot-loop
detection and recovery, max-iteration failure, tool-call error handling,
and conversation message structure.

All LLM calls and browser tool calls are mocked — no real AI or browser needed.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from consumer.agent import (
    _ACTION_TOOLS,
    _MAX_CONSECUTIVE_ERRORS,
    _MAX_CONSECUTIVE_SNAPSHOTS,
    _MAX_ITERATIONS,
    _SNAPSHOT_LOOP_REMINDER,
    _STEP_FAILED_TOOL,
    _SYSTEM_PROMPT,
    run_step,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PAGE_STATE = 'WebArea "Example" button "Submit"'  # fake but realistic snapshot text


def _llm_done(content: str = "Step completed.") -> dict[str, Any]:
    """LLM response with no tool calls — signals completion."""
    return {"tool_calls": [], "content": content}


def _llm_calls(*tool_names: str) -> dict[str, Any]:
    """LLM response that requests the given tool calls (in order)."""
    return {
        "tool_calls": [
            {"id": f"call-{i}", "name": name, "args": _default_args(name)}
            for i, name in enumerate(tool_names)
        ],
        "content": None,
    }


def _default_args(tool_name: str) -> dict[str, Any]:
    """Minimal valid args for each tool so tests don't need to repeat boilerplate."""
    return {
        "browser_navigate": {"url": "https://example.com"},
        "browser_click": {"selector": "role=button[name='Submit']"},
        "browser_type": {"selector": "role=textbox[name='Email']", "text": "user@example.com"},
        "browser_snapshot": {},
        "browser_screenshot": {},
        "browser_select_option": {"selector": "#country", "value": "Canada"},
        "browser_hover": {"selector": ".tooltip"},
        "browser_wait_for": {"selector": ".done"},
        "step_failed": {"reason": "Element not found after 3 attempts"},
    }.get(tool_name, {})


@pytest.fixture
def mock_browser() -> MagicMock:
    """A mock BrowserToolClient.

    The first call_tool call is always the pre-flight snapshot; subsequent
    calls correspond to LLM-requested tool calls. Default return value is
    _PAGE_STATE so tests that don't care about the content can ignore it.
    """
    browser = MagicMock()
    browser.list_tools.return_value = []
    browser.call_tool = AsyncMock(return_value=_PAGE_STATE)
    return browser


@pytest.fixture
def mock_llm() -> AsyncMock:
    """A mock BaseLLMAdapter. Configure .chat.side_effect per test."""
    return AsyncMock()


# ---------------------------------------------------------------------------
# Pre-flight snapshot
# ---------------------------------------------------------------------------


async def test_preflight_snapshot_is_taken_before_llm_is_called(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """browser.call_tool must be called once before llm.chat is ever called."""
    mock_llm.chat.return_value = _llm_done()
    await run_step(mock_browser, mock_llm, "click", "Click submit")
    # The pre-flight happens unconditionally, even if the LLM immediately declares done.
    mock_browser.call_tool.assert_awaited_once_with("browser_snapshot", {})


async def test_preflight_snapshot_result_is_embedded_in_user_message(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    mock_browser.call_tool.return_value = _PAGE_STATE
    mock_llm.chat.return_value = _llm_done()
    await run_step(mock_browser, mock_llm, "click", "Click submit")
    user_message = mock_llm.chat.call_args_list[0].args[0][1]
    assert user_message["role"] == "user"
    assert _PAGE_STATE in user_message["content"]


async def test_preflight_snapshot_is_recorded_in_tool_calls_made(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    mock_browser.call_tool.return_value = _PAGE_STATE
    mock_llm.chat.return_value = _llm_done()
    result = await run_step(mock_browser, mock_llm, "click", "Click submit")
    assert result["tool_calls_made"][0] == {
        "name": "browser_snapshot",
        "args": {},
        "result": _PAGE_STATE,
    }


async def test_preflight_snapshot_failure_does_not_abort_step(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """A failing pre-flight snapshot must not raise — the step should still run."""
    mock_browser.call_tool.side_effect = [
        RuntimeError("page not ready"),  # pre-flight fails
        "Clicked",  # LLM-requested click succeeds
    ]
    mock_llm.chat.side_effect = [_llm_calls("browser_click"), _llm_done()]
    result = await run_step(mock_browser, mock_llm, "click", "Click submit")
    assert result["status"] == "passed"


async def test_preflight_failure_recorded_as_unavailable_in_tool_calls_made(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    mock_browser.call_tool.side_effect = [RuntimeError("timeout"), "ok"]
    mock_llm.chat.side_effect = [_llm_calls("browser_click"), _llm_done()]
    result = await run_step(mock_browser, mock_llm, "click", "Click submit")
    assert "unavailable" in result["tool_calls_made"][0]["result"].lower()


# ---------------------------------------------------------------------------
# Normal completion
# ---------------------------------------------------------------------------


async def test_step_passes_when_llm_stops_making_tool_calls(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    mock_llm.chat.side_effect = [_llm_calls("browser_navigate"), _llm_done()]
    result = await run_step(mock_browser, mock_llm, "navigate", "Go to the homepage")
    assert result["status"] == "passed"
    assert result["error"] is None


async def test_step_fails_when_llm_makes_no_tool_calls(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """If the LLM declares done without calling any tool, the step must fail.

    Completing a step without any LLM-initiated tool call is a false positive —
    the agent never interacted with the page.
    """
    mock_llm.chat.return_value = _llm_done()
    result = await run_step(mock_browser, mock_llm, "click", "Click submit")
    assert result["status"] == "failed"
    assert result["error"] is not None
    assert "no browser action" in result["error"].lower()
    # Only the pre-flight snapshot was called — no LLM-driven tool calls.
    assert mock_browser.call_tool.await_count == 1


async def test_tool_calls_made_includes_preflight_then_llm_calls(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    mock_browser.call_tool.return_value = "ok"
    mock_llm.chat.side_effect = [
        _llm_calls("browser_navigate", "browser_snapshot"),
        _llm_done(),
    ]
    result = await run_step(mock_browser, mock_llm, "navigate", "Go to example.com")
    names = [tc["name"] for tc in result["tool_calls_made"]]
    # Pre-flight snapshot, then LLM-called navigate + snapshot, then auto-snapshot
    # (triggered because navigate is an action tool).
    assert names == ["browser_snapshot", "browser_navigate", "browser_snapshot", "browser_snapshot"]


async def test_tool_calls_made_captures_result_for_each_call(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    mock_browser.call_tool.side_effect = [_PAGE_STATE, "Navigated to https://example.com"]
    mock_llm.chat.side_effect = [_llm_calls("browser_navigate"), _llm_done()]
    result = await run_step(mock_browser, mock_llm, "navigate", "Go to example.com")
    assert result["tool_calls_made"][0]["result"] == _PAGE_STATE  # pre-flight
    assert result["tool_calls_made"][1]["result"] == "Navigated to https://example.com"


async def test_result_includes_action_and_description(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    mock_llm.chat.return_value = _llm_done()
    result = await run_step(mock_browser, mock_llm, "click", "Click the login button")
    assert result["action"] == "click"
    assert result["description"] == "Click the login button"


# ---------------------------------------------------------------------------
# Conversation structure
# ---------------------------------------------------------------------------


async def test_conversation_starts_with_system_and_user_messages(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    mock_llm.chat.return_value = _llm_done()
    await run_step(mock_browser, mock_llm, "navigate", "Go to google.com")
    first_call_messages: list[dict] = mock_llm.chat.call_args_list[0].args[0]
    assert first_call_messages[0]["role"] == "system"
    assert first_call_messages[0]["content"] == _SYSTEM_PROMPT
    assert first_call_messages[1]["role"] == "user"
    assert "navigate" in first_call_messages[1]["content"]
    assert "Go to google.com" in first_call_messages[1]["content"]


async def test_tool_results_are_fed_back_to_llm(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    mock_browser.call_tool.side_effect = [_PAGE_STATE, "Navigated to https://example.com"]
    mock_llm.chat.side_effect = [_llm_calls("browser_navigate"), _llm_done()]

    await run_step(mock_browser, mock_llm, "navigate", "Go to example.com")

    second_call_messages: list[dict] = mock_llm.chat.call_args_list[1].args[0]
    tool_result_messages = [m for m in second_call_messages if m["role"] == "tool"]
    assert len(tool_result_messages) == 1
    assert tool_result_messages[0]["content"] == "Navigated to https://example.com"


async def test_multiple_tool_results_all_fed_back(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    mock_browser.call_tool.side_effect = [_PAGE_STATE, "result-A", "result-B"]
    mock_llm.chat.side_effect = [
        _llm_calls("browser_navigate", "browser_snapshot"),
        _llm_done(),
    ]
    await run_step(mock_browser, mock_llm, "navigate", "Go to example.com")
    second_call_messages: list[dict] = mock_llm.chat.call_args_list[1].args[0]
    tool_results = [m["content"] for m in second_call_messages if m["role"] == "tool"]
    assert tool_results == ["result-A", "result-B"]


# ---------------------------------------------------------------------------
# Tool call error handling
# ---------------------------------------------------------------------------


async def test_tool_call_exception_is_returned_as_error_text(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """Playwright errors must be returned to the LLM as text, not raised as exceptions."""
    mock_browser.call_tool.side_effect = [_PAGE_STATE, TimeoutError("element not found")]
    mock_llm.chat.side_effect = [_llm_calls("browser_click"), _llm_done()]

    result = await run_step(mock_browser, mock_llm, "click", "Click submit")

    assert result["status"] == "passed"  # LLM declared done — code honours that
    click_result = result["tool_calls_made"][1]  # [0] is the pre-flight snapshot
    assert "ERROR" in click_result["result"]
    assert "element not found" in click_result["result"]


async def test_tool_call_error_text_is_sent_back_to_llm(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """The LLM must see the error message so it can retry with a different selector."""
    mock_browser.call_tool.side_effect = [_PAGE_STATE, TimeoutError("Timeout 30000ms exceeded")]
    mock_llm.chat.side_effect = [_llm_calls("browser_click"), _llm_done()]

    await run_step(mock_browser, mock_llm, "click", "Click submit")

    second_call_messages: list[dict] = mock_llm.chat.call_args_list[1].args[0]
    tool_result = next(m for m in second_call_messages if m["role"] == "tool")
    assert "Timeout 30000ms exceeded" in tool_result["content"]


# ---------------------------------------------------------------------------
# Snapshot loop detection
# ---------------------------------------------------------------------------


async def test_snapshot_loop_injects_reminder_after_consecutive_snapshots(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """After _MAX_CONSECUTIVE_SNAPSHOTS snapshots in a row, a reminder is injected."""
    mock_llm.chat.side_effect = [
        *[_llm_calls("browser_snapshot")] * _MAX_CONSECUTIVE_SNAPSHOTS,
        _llm_calls("browser_click"),  # reminder worked — LLM acts
        _llm_done(),
    ]
    await run_step(mock_browser, mock_llm, "click", "Click submit")

    all_messages: list[dict] = mock_llm.chat.call_args_list[-1].args[0]
    reminder_messages = [m for m in all_messages if m.get("content") == _SNAPSHOT_LOOP_REMINDER]
    assert len(reminder_messages) >= 1
    assert reminder_messages[0]["role"] == "user"


async def test_snapshot_loop_reminder_is_not_injected_below_threshold(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """Fewer than _MAX_CONSECUTIVE_SNAPSHOTS in a row must NOT trigger the reminder."""
    calls = [_llm_calls("browser_snapshot")] * (_MAX_CONSECUTIVE_SNAPSHOTS - 1)
    calls.append(_llm_done())
    mock_llm.chat.side_effect = calls

    await run_step(mock_browser, mock_llm, "snapshot", "Check the page")

    all_sent_messages: list[dict] = mock_llm.chat.call_args_list[-1].args[0]
    reminder_messages = [
        m for m in all_sent_messages if m.get("content") == _SNAPSHOT_LOOP_REMINDER
    ]
    assert reminder_messages == []


async def test_consecutive_snapshot_counter_resets_after_non_snapshot_tool(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """A non-snapshot tool call resets the counter so a later burst doesn't mis-fire."""
    pre = [_llm_calls("browser_snapshot")] * (_MAX_CONSECUTIVE_SNAPSHOTS - 1)
    reset = [_llm_calls("browser_click")]
    post = [_llm_calls("browser_snapshot")] * (_MAX_CONSECUTIVE_SNAPSHOTS - 1)
    mock_llm.chat.side_effect = [*pre, *reset, *post, _llm_done()]

    await run_step(mock_browser, mock_llm, "click", "Click submit")

    all_sent_messages: list[dict] = mock_llm.chat.call_args_list[-1].args[0]
    reminder_messages = [
        m for m in all_sent_messages if m.get("content") == _SNAPSHOT_LOOP_REMINDER
    ]
    assert reminder_messages == []


async def test_snapshot_loop_guard_discards_stuck_tool_calls(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """When the guard fires, the triggering batch of snapshot calls is discarded.

    Total browser calls = 1 (pre-flight) + (_MAX_CONSECUTIVE_SNAPSHOTS - 1) loop
    snapshots that ran before the guard fired. The batch that triggered the guard
    is dropped without executing.
    """
    mock_llm.chat.side_effect = [
        *[_llm_calls("browser_snapshot")] * _MAX_CONSECUTIVE_SNAPSHOTS,
        _llm_done(),
    ]
    await run_step(mock_browser, mock_llm, "snapshot", "Check page")
    expected = 1 + (_MAX_CONSECUTIVE_SNAPSHOTS - 1)  # pre-flight + pre-guard loop calls
    assert mock_browser.call_tool.await_count == expected


# ---------------------------------------------------------------------------
# Max iterations
# ---------------------------------------------------------------------------


async def test_step_fails_when_max_iterations_exceeded(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    mock_llm.chat.return_value = _llm_calls("browser_snapshot")
    result = await run_step(mock_browser, mock_llm, "navigate", "Go somewhere")
    assert result["status"] == "failed"
    assert str(_MAX_ITERATIONS) in result["error"]


async def test_llm_called_at_least_max_iterations_times_before_failure(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    mock_llm.chat.return_value = _llm_calls("browser_snapshot")
    await run_step(mock_browser, mock_llm, "navigate", "Go somewhere")
    assert mock_llm.chat.await_count >= _MAX_ITERATIONS


# ---------------------------------------------------------------------------
# Unexpected exceptions
# ---------------------------------------------------------------------------


async def test_unexpected_llm_exception_marks_step_failed(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    mock_llm.chat.side_effect = RuntimeError("network error")
    result = await run_step(mock_browser, mock_llm, "navigate", "Go somewhere")
    assert result["status"] == "failed"
    assert "network error" in result["error"]


async def test_unexpected_llm_exception_tool_calls_made_includes_preflight_and_executed(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """tool_calls_made must contain the pre-flight, executed calls, and auto-snapshot."""
    mock_browser.call_tool.side_effect = [
        _PAGE_STATE,  # pre-flight snapshot
        "Navigated to https://example.com",  # browser_navigate
        _PAGE_STATE,  # auto-snapshot after navigate
    ]
    mock_llm.chat.side_effect = [_llm_calls("browser_navigate"), RuntimeError("crash")]

    result = await run_step(mock_browser, mock_llm, "navigate", "Go somewhere")

    names = [tc["name"] for tc in result["tool_calls_made"]]
    assert names == ["browser_snapshot", "browser_navigate", "browser_snapshot"]


# ---------------------------------------------------------------------------
# Explicit step_failed tool
# ---------------------------------------------------------------------------


async def test_step_failed_tool_is_injected_into_llm_tool_list(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """run_step must always pass step_failed as the first tool to the LLM."""
    mock_llm.chat.return_value = _llm_done()
    await run_step(mock_browser, mock_llm, "click", "Click submit")
    tools_passed: list[dict] = mock_llm.chat.call_args_list[0].args[1]
    assert tools_passed[0]["name"] == "step_failed"


async def test_step_failed_tool_schema_matches_constant(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """The injected step_failed schema must be the canonical _STEP_FAILED_TOOL constant."""
    mock_llm.chat.return_value = _llm_done()
    await run_step(mock_browser, mock_llm, "click", "Click submit")
    tools_passed: list[dict] = mock_llm.chat.call_args_list[0].args[1]
    assert tools_passed[0] == _STEP_FAILED_TOOL


async def test_step_failed_call_marks_step_as_failed(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """When the LLM calls step_failed the step result status must be 'failed'."""
    mock_llm.chat.return_value = _llm_calls("step_failed")
    result = await run_step(mock_browser, mock_llm, "click", "Click a missing button")
    assert result["status"] == "failed"


async def test_step_failed_reason_appears_in_error_field(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """The reason passed to step_failed must be surfaced in result['error']."""
    reason = "Button 'Pay Now' not found after 3 selector attempts"
    mock_llm.chat.return_value = {
        "tool_calls": [{"id": "c0", "name": "step_failed", "args": {"reason": reason}}],
        "content": None,
    }
    result = await run_step(mock_browser, mock_llm, "click", "Click pay button")
    assert result["error"] is not None
    assert reason in result["error"]


async def test_step_failed_is_recorded_in_tool_calls_made(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """step_failed must appear in tool_calls_made so the test report shows it was called."""
    mock_llm.chat.return_value = _llm_calls("step_failed")
    result = await run_step(mock_browser, mock_llm, "click", "Click missing button")
    names = [tc["name"] for tc in result["tool_calls_made"]]
    assert "step_failed" in names


async def test_step_failed_does_not_forward_to_browser(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """step_failed must be handled in-loop — browser.call_tool must NOT be called for it."""
    mock_llm.chat.return_value = _llm_calls("step_failed")
    await run_step(mock_browser, mock_llm, "click", "Click missing button")
    # Only the pre-flight snapshot should have reached the browser.
    mock_browser.call_tool.assert_awaited_once_with("browser_snapshot", {})


async def test_step_failed_stops_processing_remaining_tool_calls_in_same_batch(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """Any tool calls after step_failed in the same batch must be ignored."""
    mock_llm.chat.return_value = {
        "tool_calls": [
            {"id": "c0", "name": "step_failed", "args": {"reason": "impossible"}},
            {"id": "c1", "name": "browser_click", "args": {"selector": "role=button[name='X']"}},
        ],
        "content": None,
    }
    await run_step(mock_browser, mock_llm, "click", "Click something")
    # browser_click must never have been called (only pre-flight snapshot).
    mock_browser.call_tool.assert_awaited_once_with("browser_snapshot", {})


async def test_step_failed_stops_the_agent_loop(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """After step_failed the LLM must NOT be called again."""
    mock_llm.chat.return_value = _llm_calls("step_failed")
    await run_step(mock_browser, mock_llm, "click", "Click missing button")
    mock_llm.chat.assert_awaited_once()


# ---------------------------------------------------------------------------
# System prompt content
# ---------------------------------------------------------------------------


def test_system_prompt_bans_recovery_navigation() -> None:
    """The prompt must explicitly forbid using browser_navigate to recover."""
    assert "NEVER call browser_navigate" in _SYSTEM_PROMPT


def test_system_prompt_instructs_step_failed_as_recovery_alternative() -> None:
    assert "step_failed" in _SYSTEM_PROMPT


def test_action_tools_constant_contains_expected_tools() -> None:
    assert "browser_navigate" in _ACTION_TOOLS
    assert "browser_click" in _ACTION_TOOLS
    assert "browser_type" in _ACTION_TOOLS
    assert "browser_select_option" in _ACTION_TOOLS
    assert "browser_hover" in _ACTION_TOOLS
    assert "browser_wait_for" in _ACTION_TOOLS


def test_action_tools_constant_excludes_read_only_tools() -> None:
    assert "browser_snapshot" not in _ACTION_TOOLS
    assert "browser_screenshot" not in _ACTION_TOOLS
    assert "step_failed" not in _ACTION_TOOLS


# ---------------------------------------------------------------------------
# Auto-snapshot after action tools
# ---------------------------------------------------------------------------


async def test_auto_snapshot_injected_after_action_tool(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """A browser_snapshot must be appended to tool_calls_made after every action tool."""
    mock_browser.call_tool.return_value = "ok"
    mock_llm.chat.side_effect = [_llm_calls("browser_click"), _llm_done()]
    result = await run_step(mock_browser, mock_llm, "click", "Click submit")
    names = [tc["name"] for tc in result["tool_calls_made"]]
    # pre-flight, click, auto-snapshot
    click_idx = names.index("browser_click")
    assert names[click_idx + 1] == "browser_snapshot"


async def test_auto_snapshot_not_injected_after_snapshot_only_iteration(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """An iteration that only calls browser_snapshot must NOT trigger an extra auto-snapshot."""
    mock_browser.call_tool.return_value = "ok"
    mock_llm.chat.side_effect = [_llm_calls("browser_snapshot"), _llm_done()]
    result = await run_step(mock_browser, mock_llm, "assert", "Heading is visible")
    names = [tc["name"] for tc in result["tool_calls_made"]]
    # Only preflight + LLM-called snapshot — no auto-snapshot.
    assert names.count("browser_snapshot") == 2


async def test_auto_snapshot_result_injected_as_user_message(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """The auto-snapshot must appear as a user message in the next LLM call."""
    auto_snap_text = 'WebArea "Confirmation" heading "Success"'
    mock_browser.call_tool.side_effect = [
        _PAGE_STATE,  # pre-flight
        "Navigated",  # browser_navigate
        auto_snap_text,  # auto-snapshot
    ]
    mock_llm.chat.side_effect = [_llm_calls("browser_navigate"), _llm_done()]
    await run_step(mock_browser, mock_llm, "navigate", "Go to page")

    second_call_messages: list[dict] = mock_llm.chat.call_args_list[1].args[0]
    user_messages = [m for m in second_call_messages if m["role"] == "user"]
    auto_msg = next(
        (m for m in user_messages if "[Page state after action]" in m.get("content", "")),
        None,
    )
    assert auto_msg is not None
    assert auto_snap_text in auto_msg["content"]


async def test_auto_snapshot_failure_is_recorded_but_does_not_abort_step(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """A failing auto-snapshot must be recorded gracefully; the step must still pass."""
    mock_browser.call_tool.side_effect = [
        _PAGE_STATE,  # pre-flight
        "Clicked",  # browser_click
        RuntimeError("page gone"),  # auto-snapshot fails
    ]
    mock_llm.chat.side_effect = [_llm_calls("browser_click"), _llm_done()]
    result = await run_step(mock_browser, mock_llm, "click", "Click submit")
    assert result["status"] == "passed"
    auto_snap = result["tool_calls_made"][2]
    assert auto_snap["name"] == "browser_snapshot"
    assert "auto-snapshot failed" in auto_snap["result"]


# ---------------------------------------------------------------------------
# Consecutive error abort
# ---------------------------------------------------------------------------


async def test_step_aborted_after_max_consecutive_errors(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """The step must fail once _MAX_CONSECUTIVE_ERRORS tool calls error in a row."""
    # Each iteration: click errors, then auto-snapshot succeeds.
    # After _MAX_CONSECUTIVE_ERRORS click errors the loop aborts before the next auto-snapshot.
    side_effects: list[Any] = [_PAGE_STATE]  # pre-flight
    for _ in range(_MAX_CONSECUTIVE_ERRORS - 1):
        side_effects.append(TimeoutError("timeout"))  # click error
        side_effects.append(_PAGE_STATE)  # auto-snapshot
    side_effects.append(TimeoutError("timeout"))  # final error → abort (no auto-snapshot)

    mock_browser.call_tool.side_effect = side_effects
    mock_llm.chat.return_value = _llm_calls("browser_click")

    result = await run_step(mock_browser, mock_llm, "click", "Click submit")
    assert result["status"] == "failed"
    assert str(_MAX_CONSECUTIVE_ERRORS) in result["error"]


async def test_step_not_aborted_below_consecutive_error_threshold(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """Fewer than _MAX_CONSECUTIVE_ERRORS errors in a row must not abort the step."""
    below = _MAX_CONSECUTIVE_ERRORS - 1
    side_effects: list[Any] = [_PAGE_STATE]  # pre-flight
    for _ in range(below):
        side_effects.append(TimeoutError("timeout"))  # error
        side_effects.append(_PAGE_STATE)  # auto-snapshot
    side_effects.append("Clicked!")  # success — counter resets
    side_effects.append(_PAGE_STATE)  # auto-snapshot after success

    mock_llm.chat.side_effect = [
        *[_llm_calls("browser_click")] * below,
        _llm_calls("browser_click"),
        _llm_done(),
    ]
    mock_browser.call_tool.side_effect = side_effects

    result = await run_step(mock_browser, mock_llm, "click", "Click submit")
    assert result["status"] == "passed"


async def test_consecutive_error_counter_resets_after_successful_tool_call(
    mock_browser: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """A successful tool call must reset the consecutive error counter."""
    below = _MAX_CONSECUTIVE_ERRORS - 1
    side_effects: list[Any] = [_PAGE_STATE]
    for _ in range(below):
        side_effects.append(TimeoutError("t"))
        side_effects.append(_PAGE_STATE)
    # Success resets the counter, then we get below-threshold errors again.
    side_effects.append("Clicked!")  # success
    side_effects.append(_PAGE_STATE)  # auto-snapshot
    for _ in range(below):
        side_effects.append(TimeoutError("t"))
        side_effects.append(_PAGE_STATE)
    side_effects.append("Clicked!")  # final success
    side_effects.append(_PAGE_STATE)

    mock_llm.chat.side_effect = [
        *[_llm_calls("browser_click")] * below,
        _llm_calls("browser_click"),  # success
        *[_llm_calls("browser_click")] * below,
        _llm_calls("browser_click"),  # success
        _llm_done(),
    ]
    mock_browser.call_tool.side_effect = side_effects

    result = await run_step(mock_browser, mock_llm, "click", "Click submit")
    assert result["status"] == "passed"
