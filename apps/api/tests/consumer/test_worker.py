
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from consumer.be_client import BEClient
from consumer.worker import handle_message
from tests.consumer.conftest import MockMessage


def make_message(payload: dict) -> MockMessage:
    return MockMessage(json.dumps(payload).encode())


def make_run_message(run_id: str = "run-1", test_case_id: str = "case-1") -> MockMessage:
    return make_message({"run_id": run_id, "test_case_id": test_case_id})


async def test_valid_message_is_acked(valid_message, mock_client):
    await handle_message(valid_message, mock_client)

    assert valid_message.acked is True
    assert valid_message.nacked is False


async def test_valid_message_fetches_run_details(valid_message, mock_client):
    await handle_message(valid_message, mock_client)

    mock_client.get_test_run.assert_awaited_once_with("run-abc")


async def test_valid_message_posts_results(valid_message, mock_client):
    await handle_message(valid_message, mock_client)

    mock_client.update_run_result.assert_awaited_once()
    call_args = mock_client.update_run_result.call_args
    run_id, result_payload = call_args.args
    assert run_id == "run-abc"
    assert result_payload["status"] == "passed"
    assert isinstance(result_payload["step_results"], list)


async def test_valid_message_step_count_matches_payload(mock_client):
    msg = make_run_message()
    mock_client.get_test_run.return_value = {
        **mock_client.get_test_run.return_value,
        "test_case_payload": {
            "steps": [
                {"action": "goto",  "params": {"url": "https://a.com"}},
                {"action": "click", "params": {"selector": "#b"}},
                {"action": "fill",  "params": {"selector": "#c", "value": "d"}},
            ]
        },
    }

    await handle_message(msg, mock_client)

    result_payload = mock_client.update_run_result.call_args.args[1]
    assert len(result_payload["step_results"]) == 3


async def test_invalid_json_nacks_without_requeue():
    msg = MockMessage(b"not-valid-json")

    await handle_message(msg, AsyncMock(spec=BEClient))

    assert msg.nacked is True
    assert msg.nack_requeue is False
    assert msg.acked is False


async def test_missing_run_id_nacks_without_requeue():
    msg = make_message({"test_case_id": "case-1"})

    await handle_message(msg, AsyncMock())

    assert msg.nacked is True
    assert msg.nack_requeue is False


async def test_empty_body_nacks_without_requeue():
    msg = MockMessage(b"")

    await handle_message(msg, AsyncMock())

    assert msg.nacked is True
    assert msg.nack_requeue is False


async def test_get_test_run_raises_nacks_with_requeue(mock_client):
    msg = make_run_message()
    mock_client.get_test_run.side_effect = httpx.ConnectError("BE unavailable")

    with pytest.raises(httpx.ConnectError):
        await handle_message(msg, mock_client)

    assert msg.nacked is True
    assert msg.nack_requeue is True
    assert msg.acked is False


async def test_update_run_result_raises_nacks_with_requeue(mock_client):
    msg = make_run_message()
    mock_client.update_run_result.side_effect = httpx.ConnectError("BE unavailable")

    with pytest.raises(httpx.ConnectError):
        await handle_message(msg, mock_client)

    assert msg.nacked is True
    assert msg.nack_requeue is True
    assert msg.acked is False


async def test_get_test_run_http_error_nacks_with_requeue(mock_client):
    msg = make_run_message()
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_client.get_test_run.side_effect = httpx.HTTPStatusError(
        "503", request=MagicMock(), response=mock_response
    )

    with pytest.raises(httpx.HTTPStatusError):
        await handle_message(msg, mock_client)

    assert msg.nacked is True
    assert msg.nack_requeue is True
    assert msg.acked is False


async def test_get_test_run_4xx_nacks_without_requeue(mock_client):
    msg = make_run_message()
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_client.get_test_run.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=mock_response
    )

    with pytest.raises(httpx.HTTPStatusError):
        await handle_message(msg, mock_client)

    assert msg.nacked is True
    assert msg.nack_requeue is False
    assert msg.acked is False


async def test_malformed_message_does_not_call_client():
    msg = MockMessage(b"garbage")
    client = AsyncMock()

    await handle_message(msg, client)

    client.get_test_run.assert_not_awaited()
    client.update_run_result.assert_not_awaited()
