
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from consumer.executor import execute_test
from consumer.storage import LocalStorageBackend, S3StorageBackend, create_storage_backend
from tests.consumer.conftest import MockMessage
from consumer.worker import handle_message


async def test_local_backend_creates_file(tmp_path):
    source = tmp_path / "input.webm"
    source.write_bytes(b"recording-data")

    storage_dir = tmp_path / "recordings"
    backend = LocalStorageBackend(recordings_dir=storage_dir, base_url="http://localhost:8000")

    url = await backend.upload(source, "run-abc.webm")

    assert (storage_dir / "run-abc.webm").exists()
    assert (storage_dir / "run-abc.webm").read_bytes() == b"recording-data"
    assert url == "http://localhost:8000/recordings/run-abc.webm"


async def test_local_backend_url_format(tmp_path):
    source = tmp_path / "f.webm"
    source.write_bytes(b"x")
    backend = LocalStorageBackend(recordings_dir=tmp_path / "r", base_url="http://localhost:8000")

    url = await backend.upload(source, "run-xyz.webm")

    assert url.startswith("http://localhost:8000/recordings/")
    assert url.endswith("run-xyz.webm")


async def test_local_backend_strips_trailing_slash_from_base_url(tmp_path):
    source = tmp_path / "f.webm"
    source.write_bytes(b"x")
    backend = LocalStorageBackend(
        recordings_dir=tmp_path / "r",
        base_url="http://localhost:8000/",
    )

    url = await backend.upload(source, "run-1.webm")

    assert "//recordings" not in url


async def test_local_backend_creates_recordings_dir_if_missing(tmp_path):
    source = tmp_path / "f.webm"
    source.write_bytes(b"x")
    storage_dir = tmp_path / "does" / "not" / "exist"

    backend = LocalStorageBackend(recordings_dir=storage_dir, base_url="http://localhost:8000")
    await backend.upload(source, "run-1.webm")

    assert storage_dir.exists()


async def test_local_backend_overwrites_existing_file(tmp_path):
    storage_dir = tmp_path / "recordings"
    storage_dir.mkdir()
    (storage_dir / "run-1.webm").write_bytes(b"old-data")

    source = tmp_path / "new.webm"
    source.write_bytes(b"new-data")

    backend = LocalStorageBackend(recordings_dir=storage_dir, base_url="http://localhost:8000")
    await backend.upload(source, "run-1.webm")

    assert (storage_dir / "run-1.webm").read_bytes() == b"new-data"


async def test_s3_backend_raises_not_implemented(tmp_path):
    source = tmp_path / "f.webm"
    source.write_bytes(b"x")
    backend = S3StorageBackend(bucket="my-bucket", region="us-east-1")

    with pytest.raises(NotImplementedError):
        await backend.upload(source, "run-1.webm")


def test_factory_returns_local_backend(tmp_path):
    backend = create_storage_backend(
        backend="local",
        recordings_dir=tmp_path / "recordings",
        base_url="http://localhost:8000",
    )
    assert isinstance(backend, LocalStorageBackend)


def test_factory_returns_s3_backend(tmp_path):
    backend = create_storage_backend(
        backend="s3",
        recordings_dir=tmp_path / "recordings",
        base_url="http://localhost:8000",
        s3_bucket="my-bucket",
        s3_region="eu-west-1",
    )
    assert isinstance(backend, S3StorageBackend)


def test_factory_raises_on_unknown_backend(tmp_path):
    with pytest.raises(ValueError, match="Unknown storage backend"):
        create_storage_backend(
            backend="gcs",
            recordings_dir=tmp_path,
            base_url="http://localhost:8000",
        )


BASE_LLM_CONFIG = {"provider": "openai", "api_key": "sk-test", "model_name": "gpt-4"}

PASSED_STEP_RESULT = {"status": "passed", "tool_calls_made": [], "error": None}


def make_mcp_patcher():
    from unittest.mock import MagicMock

    mock_mcp = AsyncMock()
    mock_mcp_ctx = MagicMock()
    mock_mcp_ctx.__aenter__ = AsyncMock(return_value=mock_mcp)
    mock_mcp_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_mcp_cls = MagicMock(return_value=mock_mcp_ctx)
    return patch("consumer.executor.MCPClient", mock_mcp_cls)


async def test_executor_returns_recording_url_when_storage_provided(tmp_path):
    trace_zip = tmp_path / "trace.zip"
    trace_zip.write_bytes(b"fake-trace")

    backend = LocalStorageBackend(recordings_dir=tmp_path / "r", base_url="http://localhost:8000")
    run_detail = {"id": "run-abc", "test_case_payload": {"steps": []}, "llm_config": BASE_LLM_CONFIG}

    mcp_patcher = make_mcp_patcher()
    with (
        mcp_patcher,
        patch("consumer.executor.run_step", AsyncMock(return_value=PASSED_STEP_RESULT)),
        patch("consumer.executor.create_adapter", return_value=AsyncMock()),
        patch("consumer.executor._find_trace", return_value=trace_zip),
    ):
        result = await execute_test(run_detail, storage=backend)

    assert result["recording_url"] is not None
    assert "run-abc-trace.zip" in result["recording_url"]


async def test_executor_recording_file_is_created(tmp_path):
    trace_zip = tmp_path / "trace.zip"
    trace_zip.write_bytes(b"fake-trace")

    storage_dir = tmp_path / "recordings"
    backend = LocalStorageBackend(recordings_dir=storage_dir, base_url="http://localhost:8000")
    run_detail = {"id": "run-xyz", "test_case_payload": {"steps": []}, "llm_config": BASE_LLM_CONFIG}

    mcp_patcher = make_mcp_patcher()
    with (
        mcp_patcher,
        patch("consumer.executor.run_step", AsyncMock(return_value=PASSED_STEP_RESULT)),
        patch("consumer.executor.create_adapter", return_value=AsyncMock()),
        patch("consumer.executor._find_trace", return_value=trace_zip),
    ):
        await execute_test(run_detail, storage=backend)

    assert (storage_dir / "run-xyz-trace.zip").exists()


async def test_executor_no_storage_returns_null_recording_url():
    run_detail = {"id": "run-abc", "test_case_payload": {"steps": []}, "llm_config": BASE_LLM_CONFIG}

    mcp_patcher = make_mcp_patcher()
    with (
        mcp_patcher,
        patch("consumer.executor.run_step", AsyncMock(return_value=PASSED_STEP_RESULT)),
        patch("consumer.executor.create_adapter", return_value=AsyncMock()),
    ):
        result = await execute_test(run_detail, storage=None)

    assert result["recording_url"] is None


async def test_executor_recording_url_in_result_with_steps(tmp_path):
    trace_zip = tmp_path / "trace.zip"
    trace_zip.write_bytes(b"fake-trace")

    backend = LocalStorageBackend(recordings_dir=tmp_path / "r", base_url="http://localhost:8000")
    run_detail = {
        "id": "run-1",
        "llm_config": BASE_LLM_CONFIG,
        "test_case_payload": {
            "steps": [
                {"action": "goto", "description": "Navigate to the homepage"},
                {"action": "click", "description": "Click the submit button"},
            ]
        },
    }

    mcp_patcher = make_mcp_patcher()
    with (
        mcp_patcher,
        patch("consumer.executor.run_step", AsyncMock(return_value=PASSED_STEP_RESULT)),
        patch("consumer.executor.create_adapter", return_value=AsyncMock()),
        patch("consumer.executor._find_trace", return_value=trace_zip),
    ):
        result = await execute_test(run_detail, storage=backend)

    assert result["status"] == "passed"
    assert len(result["step_results"]) == 2
    assert result["recording_url"] is not None


async def test_worker_passes_recording_url_to_be(mock_client, tmp_path):
    storage = LocalStorageBackend(recordings_dir=tmp_path / "r", base_url="http://localhost:8000")
    msg = MockMessage(json.dumps({"run_id": "run-abc", "test_case_id": "case-abc"}).encode())

    # Override the autouse mock to return a recording_url when storage is provided
    async def _fake_with_recording(run_detail, storage=None):
        run_id = run_detail.get("id", "run")
        recording_url = (
            f"http://localhost:8000/recordings/{run_id}-trace.zip"
            if storage is not None
            else None
        )
        return {
            "status": "passed",
            "step_results": [],
            "recording_url": recording_url,
            "error": None,
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_at": "2026-01-01T00:00:00+00:00",
        }

    with patch("consumer.worker.execute_test", side_effect=_fake_with_recording):
        await handle_message(msg, mock_client, storage=storage)

    result_payload = mock_client.update_run_result.call_args.args[1]
    assert result_payload["recording_url"] is not None
    assert "run-abc-trace.zip" in result_payload["recording_url"]


async def test_worker_no_storage_passes_null_recording_url(mock_client):
    msg = MockMessage(json.dumps({"run_id": "run-abc", "test_case_id": "case-abc"}).encode())

    await handle_message(msg, mock_client, storage=None)

    result_payload = mock_client.update_run_result.call_args.args[1]
    assert result_payload["recording_url"] is None
