from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from consumer.be_client import BEClient


def _make_step_results(run_detail: dict[str, Any]) -> list[dict[str, Any]]:
    steps = (run_detail.get("test_case_payload") or {}).get("steps", [])
    return [
        {
            "index": i,
            "action": s.get("action", "unknown"),
            "description": s.get("description", ""),
            "group": None,
            "status": "passed",
            "duration_ms": 0,
            "logs": [],
            "screenshot_path": None,
            "error": None,
        }
        for i, s in enumerate(steps)
    ]


@pytest.fixture(autouse=True)
def mock_execute_test():
    async def _fake(run_detail: dict[str, Any], storage: Any = None) -> dict[str, Any]:
        return {
            "status": "passed",
            "step_results": _make_step_results(run_detail),
            "recording_url": None,
            "error": None,
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_at": "2026-01-01T00:00:00+00:00",
        }

    with patch("consumer.worker.execute_test", side_effect=_fake):
        yield


class MockMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.acked: bool = False
        self.nacked: bool = False
        self.nack_requeue: bool | None = None

    async def nack(self, requeue: bool = True) -> None:
        self.nacked = True
        self.nack_requeue = requeue

    def process(self, requeue: bool = True) -> "_ProcessContext":
        return self._ProcessContext(self, requeue)

    class _ProcessContext:
        def __init__(self, msg: "MockMessage", requeue: bool) -> None:
            self._msg = msg
            self._requeue = requeue

        async def __aenter__(self) -> "MockMessage._ProcessContext":
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
            if exc_type is None:
                self._msg.acked = True
            else:
                await self._msg.nack(requeue=self._requeue)
            return False


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock(spec=BEClient)
    client.get_test_run.return_value = {
        "id": "run-abc",
        "test_case_id": "case-abc",
        "test_group_run_id": None,
        "status": "queued",
        "browser": "chromium",
        "base_url_override": None,
        "viewport_width": 1280,
        "viewport_height": 720,
        "test_case_payload": {
            "steps": [
                {"action": "goto", "description": "Navigate to the homepage"},
                {"action": "click", "description": "Click the submit button"},
            ]
        },
        "llm_config": {
            "provider": "openai",
            "api_key": "sk-test",
            "model_name": "gpt-4",
        },
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    client.update_run_result.return_value = None
    return client


@pytest.fixture
def valid_message() -> MockMessage:
    import json

    return MockMessage(json.dumps({"run_id": "run-abc", "test_case_id": "case-abc"}).encode())
