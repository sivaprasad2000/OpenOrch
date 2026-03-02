
import asyncio
import json
from unittest.mock import AsyncMock, call

import pytest

from consumer.be_client import BEClient
from consumer.worker import handle_message
from tests.consumer.conftest import MockMessage


def make_message(run_id: str, test_case_id: str = "case-1") -> MockMessage:
    return MockMessage(json.dumps({"run_id": run_id, "test_case_id": test_case_id}).encode())


def make_run_detail(run_id: str, steps: list | None = None) -> dict:
    return {
        "id": run_id,
        "test_case_id": "case-1",
        "test_group_run_id": None,
        "status": "queued",
        "browser": "chromium",
        "base_url_override": None,
        "viewport_width": 1280,
        "viewport_height": 720,
        "test_case_payload": {"steps": steps or []},
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


async def drain(queue: asyncio.Queue, client: BEClient) -> list[MockMessage]:
    processed: list[MockMessage] = []
    while not queue.empty():
        msg: MockMessage = await queue.get()
        processed.append(msg)
        await handle_message(msg, client)
        queue.task_done()
    return processed


async def test_single_message_processed_and_acked(mock_client):
    queue: asyncio.Queue = asyncio.Queue()
    await queue.put(make_message("run-1"))

    processed = await drain(queue, mock_client)

    assert len(processed) == 1
    assert processed[0].acked is True
    assert processed[0].nacked is False
    mock_client.get_test_run.assert_awaited_once_with("run-1")
    mock_client.update_run_result.assert_awaited_once()


async def test_multiple_messages_all_acked(mock_client):
    queue: asyncio.Queue = asyncio.Queue()
    run_ids = ["run-1", "run-2", "run-3"]
    for rid in run_ids:
        await queue.put(make_message(rid))

    mock_client.get_test_run.side_effect = [make_run_detail(rid) for rid in run_ids]

    processed = await drain(queue, mock_client)

    assert len(processed) == 3
    assert all(m.acked for m in processed)
    assert mock_client.get_test_run.await_count == 3
    assert mock_client.update_run_result.await_count == 3


async def test_multiple_messages_correct_run_ids_fetched(mock_client):
    queue: asyncio.Queue = asyncio.Queue()
    run_ids = ["run-A", "run-B", "run-C"]
    for rid in run_ids:
        await queue.put(make_message(rid))

    mock_client.get_test_run.side_effect = [make_run_detail(rid) for rid in run_ids]

    await drain(queue, mock_client)

    fetched = [c.args[0] for c in mock_client.get_test_run.call_args_list]
    assert fetched == run_ids


async def test_multiple_messages_correct_run_ids_reported(mock_client):
    queue: asyncio.Queue = asyncio.Queue()
    run_ids = ["run-X", "run-Y"]
    for rid in run_ids:
        await queue.put(make_message(rid))

    mock_client.get_test_run.side_effect = [make_run_detail(rid) for rid in run_ids]

    await drain(queue, mock_client)

    reported = [c.args[0] for c in mock_client.update_run_result.call_args_list]
    assert reported == run_ids


async def test_malformed_message_does_not_block_valid_ones(mock_client):
    queue: asyncio.Queue = asyncio.Queue()
    good_1 = make_message("run-1")
    bad = MockMessage(b"{{not-json")
    good_2 = make_message("run-2")

    for msg in [good_1, bad, good_2]:
        await queue.put(msg)

    mock_client.get_test_run.side_effect = [
        make_run_detail("run-1"),
        make_run_detail("run-2"),
    ]

    processed = await drain(queue, mock_client)

    assert processed[0].acked is True
    assert processed[1].nacked is True
    assert processed[1].nack_requeue is False
    assert processed[2].acked is True


async def test_empty_queue_produces_no_calls(mock_client):
    queue: asyncio.Queue = asyncio.Queue()

    processed = await drain(queue, mock_client)

    assert processed == []
    mock_client.get_test_run.assert_not_awaited()
    mock_client.update_run_result.assert_not_awaited()


async def test_pipeline_step_results_written_to_be(mock_client):
    steps = [
        {"action": "goto",  "params": {"url": "https://example.com"}},
        {"action": "click", "params": {"selector": "#login"}},
    ]
    mock_client.get_test_run.return_value = make_run_detail("run-1", steps=steps)

    queue: asyncio.Queue = asyncio.Queue()
    await queue.put(make_message("run-1"))

    await drain(queue, mock_client)

    result_payload = mock_client.update_run_result.call_args.args[1]
    assert result_payload["status"] == "passed"
    assert len(result_payload["step_results"]) == 2
    assert result_payload["step_results"][0]["action"] == "goto"
    assert result_payload["step_results"][1]["action"] == "click"


async def test_pipeline_empty_payload_writes_empty_steps(mock_client):
    mock_client.get_test_run.return_value = make_run_detail("run-1", steps=[])

    queue: asyncio.Queue = asyncio.Queue()
    await queue.put(make_message("run-1"))

    await drain(queue, mock_client)

    result_payload = mock_client.update_run_result.call_args.args[1]
    assert result_payload["step_results"] == []


async def test_concurrent_workers_process_all_messages(mock_client):
    queue: asyncio.Queue = asyncio.Queue()
    run_ids = [f"run-{i}" for i in range(6)]
    for rid in run_ids:
        await queue.put(make_message(rid))

    mock_client.get_test_run.side_effect = [make_run_detail(rid) for rid in run_ids]

    async def worker() -> list[MockMessage]:
        results = []
        while not queue.empty():
            try:
                msg: MockMessage = queue.get_nowait()
                results.append(msg)
                await handle_message(msg, mock_client)
                queue.task_done()
            except asyncio.QueueEmpty:
                break
        return results

    batches = await asyncio.gather(worker(), worker())
    all_processed = batches[0] + batches[1]

    assert len(all_processed) == 6
    assert all(m.acked for m in all_processed)
    assert mock_client.get_test_run.await_count == 6
