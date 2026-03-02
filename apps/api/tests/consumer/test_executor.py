"""Tests for consumer/executor.py — agentic executor."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from consumer.executor import execute_test

BASE_LLM_CONFIG = {"provider": "openai", "api_key": "sk-test", "model_name": "gpt-4"}

NAVIGATE_STEP = {"action": "navigate", "description": "Go to the homepage"}
CLICK_STEP = {"action": "click", "description": "Click the submit button"}
TYPE_STEP = {"action": "type", "description": "Type the email address into the email field"}

PASSED_STEP_RESULT = {"status": "passed", "tool_calls_made": [], "error": None}
FAILED_STEP_RESULT = {"status": "failed", "tool_calls_made": [], "error": "Element not found"}


def run_detail(
    steps: list | None = None,
    llm_config: dict | None = BASE_LLM_CONFIG,
    run_id: str = "run-1",
) -> dict:
    payload = {} if steps is None else {"steps": steps}
    return {"id": run_id, "test_case_payload": payload, "llm_config": llm_config}


def make_service_patcher():
    """Return (mock_service_instance, patch_context) for PlaywrightService."""
    mock_service = AsyncMock()
    mock_service.list_tools.return_value = []
    mock_service.call_tool.return_value = "ok"
    mock_service_cls = MagicMock(return_value=mock_service)
    return mock_service, patch("consumer.executor.PlaywrightService", mock_service_cls)


@pytest.fixture(autouse=True)
def mock_create_adapter():
    with patch("consumer.executor.create_adapter", return_value=AsyncMock()):
        yield


# ── llm_config validation ──────────────────────────────────────────────────────


async def test_missing_llm_config_returns_failed():
    result = await execute_test({"id": "run-1", "test_case_payload": {"steps": []}})
    assert result["status"] == "failed"
    assert result["error"] is not None
    assert "llm" in result["error"].lower()
    assert result["step_results"] == []


async def test_null_llm_config_returns_failed():
    result = await execute_test(run_detail(steps=[], llm_config=None))
    assert result["status"] == "failed"


# ── basic lifecycle ────────────────────────────────────────────────────────────


async def test_empty_steps_returns_passed():
    _, patcher = make_service_patcher()
    with patcher, patch("consumer.executor.run_step", AsyncMock(return_value=PASSED_STEP_RESULT)):
        result = await execute_test(run_detail(steps=[]))

    assert result["status"] == "passed"
    assert result["step_results"] == []
    assert result["error"] is None


async def test_missing_payload_defaults_to_no_steps():
    detail = {"id": "run-1", "llm_config": BASE_LLM_CONFIG}
    _, patcher = make_service_patcher()
    with patcher, patch("consumer.executor.run_step", AsyncMock(return_value=PASSED_STEP_RESULT)):
        result = await execute_test(detail)

    assert result["status"] == "passed"
    assert result["step_results"] == []


async def test_null_payload_defaults_to_no_steps():
    detail = {"id": "run-1", "test_case_payload": None, "llm_config": BASE_LLM_CONFIG}
    _, patcher = make_service_patcher()
    with patcher, patch("consumer.executor.run_step", AsyncMock(return_value=PASSED_STEP_RESULT)):
        result = await execute_test(detail)

    assert result["status"] == "passed"
    assert result["step_results"] == []


# ── timestamps ─────────────────────────────────────────────────────────────────


async def test_timestamps_are_iso8601():
    _, patcher = make_service_patcher()
    with patcher, patch("consumer.executor.run_step", AsyncMock(return_value=PASSED_STEP_RESULT)):
        result = await execute_test(run_detail(steps=[]))

    datetime.fromisoformat(result["started_at"])
    datetime.fromisoformat(result["completed_at"])


async def test_completed_at_not_before_started_at():
    _, patcher = make_service_patcher()
    with patcher, patch("consumer.executor.run_step", AsyncMock(return_value=PASSED_STEP_RESULT)):
        result = await execute_test(run_detail(steps=[]))

    assert (
        datetime.fromisoformat(result["completed_at"])
        >= datetime.fromisoformat(result["started_at"])
    )


# ── step processing ────────────────────────────────────────────────────────────


async def test_step_count_matches_input():
    _, patcher = make_service_patcher()
    with patcher, patch("consumer.executor.run_step", AsyncMock(return_value=PASSED_STEP_RESULT)):
        result = await execute_test(run_detail(steps=[NAVIGATE_STEP, CLICK_STEP, TYPE_STEP]))

    assert len(result["step_results"]) == 3


async def test_step_fields_are_populated():
    _, patcher = make_service_patcher()
    with patcher, patch("consumer.executor.run_step", AsyncMock(return_value=PASSED_STEP_RESULT)):
        result = await execute_test(run_detail(steps=[NAVIGATE_STEP]))

    step = result["step_results"][0]
    assert step["index"] == 0
    assert step["action"] == "navigate"
    assert step["description"] == "Go to the homepage"
    assert step["status"] == "passed"
    assert isinstance(step["duration_ms"], int)
    assert step["duration_ms"] >= 0
    assert isinstance(step["started_at_seconds"], float)
    assert step["started_at_seconds"] >= 0.0
    assert step["screenshot_path"] is None
    assert step["error"] is None


async def test_step_indices_are_sequential():
    _, patcher = make_service_patcher()
    with patcher, patch("consumer.executor.run_step", AsyncMock(return_value=PASSED_STEP_RESULT)):
        result = await execute_test(run_detail(steps=[NAVIGATE_STEP, CLICK_STEP, TYPE_STEP]))

    assert [s["index"] for s in result["step_results"]] == [0, 1, 2]


async def test_step_actions_match_input():
    steps = [NAVIGATE_STEP, CLICK_STEP]
    _, patcher = make_service_patcher()
    with patcher, patch("consumer.executor.run_step", AsyncMock(return_value=PASSED_STEP_RESULT)):
        result = await execute_test(run_detail(steps=steps))

    for i, step in enumerate(steps):
        assert result["step_results"][i]["action"] == step["action"]
        assert result["step_results"][i]["description"] == step["description"]


async def test_top_level_steps_have_no_group():
    _, patcher = make_service_patcher()
    with patcher, patch("consumer.executor.run_step", AsyncMock(return_value=PASSED_STEP_RESULT)):
        result = await execute_test(run_detail(steps=[NAVIGATE_STEP]))

    assert result["step_results"][0]["group"] is None


async def test_group_steps_are_flattened():
    group_step = {
        "type": "group",
        "name": "Login Group",
        "steps": [NAVIGATE_STEP, CLICK_STEP],
    }
    mock_run_step = AsyncMock(return_value=PASSED_STEP_RESULT)
    _, patcher = make_service_patcher()
    with patcher, patch("consumer.executor.run_step", mock_run_step):
        result = await execute_test(run_detail(steps=[group_step]))

    assert len(result["step_results"]) == 2
    assert result["step_results"][0]["group"] == "Login Group"
    assert result["step_results"][1]["group"] == "Login Group"


# ── failure handling ───────────────────────────────────────────────────────────


async def test_failed_step_sets_overall_status_failed():
    _, patcher = make_service_patcher()
    with patcher, patch("consumer.executor.run_step", AsyncMock(return_value=FAILED_STEP_RESULT)):
        result = await execute_test(run_detail(steps=[CLICK_STEP]))

    assert result["status"] == "failed"
    assert result["step_results"][0]["status"] == "failed"


async def test_subsequent_steps_run_after_failed_step():
    mock_run_step = AsyncMock(side_effect=[FAILED_STEP_RESULT, PASSED_STEP_RESULT])
    _, patcher = make_service_patcher()
    with patcher, patch("consumer.executor.run_step", mock_run_step):
        result = await execute_test(run_detail(steps=[CLICK_STEP, NAVIGATE_STEP]))

    assert len(result["step_results"]) == 2
    assert result["step_results"][0]["status"] == "failed"
    assert result["step_results"][1]["status"] == "passed"


async def test_executor_crash_returns_failed():
    _, patcher = make_service_patcher()
    with (
        patcher,
        patch("consumer.executor.run_step", AsyncMock(side_effect=RuntimeError("browser crashed"))),
    ):
        result = await execute_test(run_detail(steps=[NAVIGATE_STEP]))

    assert result["status"] == "failed"
    assert "browser crashed" in result["error"]


# ── recording / storage ────────────────────────────────────────────────────────


async def test_recording_url_is_none_when_no_storage():
    _, patcher = make_service_patcher()
    with patcher, patch("consumer.executor.run_step", AsyncMock(return_value=PASSED_STEP_RESULT)):
        result = await execute_test(run_detail(steps=[]))

    assert result["recording_url"] is None


async def test_recording_url_set_when_video_found(tmp_path):
    video_file = tmp_path / "video.webm"
    video_file.write_bytes(b"fake-video")

    mock_storage = AsyncMock()
    mock_storage.upload.return_value = "https://storage.example.com/video.webm"

    _, patcher = make_service_patcher()
    with (
        patcher,
        patch("consumer.executor.run_step", AsyncMock(return_value=PASSED_STEP_RESULT)),
        patch("consumer.executor._find_file", side_effect=lambda d, p: video_file if "webm" in p else None),
    ):
        result = await execute_test(run_detail(steps=[]), storage=mock_storage)

    assert result["recording_url"] == "https://storage.example.com/video.webm"
    mock_storage.upload.assert_awaited_once()


async def test_recording_url_none_when_no_video():
    mock_storage = AsyncMock()

    _, patcher = make_service_patcher()
    with (
        patcher,
        patch("consumer.executor.run_step", AsyncMock(return_value=PASSED_STEP_RESULT)),
        patch("consumer.executor._find_file", return_value=None),
    ):
        result = await execute_test(run_detail(steps=[]), storage=mock_storage)

    assert result["recording_url"] is None
    mock_storage.upload.assert_not_awaited()
