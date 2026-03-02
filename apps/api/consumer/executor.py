"""Agentic test executor.

Drives browser automation via an LLM agent + in-process Playwright service.
Each step is described in natural language; the LLM decides which browser
tools to call to complete it.

Video and trace files are captured automatically. When stop() returns, both
files are fully finalized and ready to upload.
"""

import logging
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from consumer.agent import run_step
from consumer.config import settings
from consumer.llm_adapters import create_adapter
from consumer.playwright_service import PlaywrightService
from consumer.storage import StorageBackend
from shared.llm.types import LLMProvider

logger = logging.getLogger(__name__)


def _make_failure_result(
    error: str,
    started_at: datetime,
    step_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a standardised TestRunResultUpdate payload for early-exit failures."""
    return {
        "status": "failed",
        "step_results": step_results or [],
        "recording_url": None,
        "trace_url": None,
        "error": error,
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


async def execute_test(
    run_detail: dict[str, Any],
    storage: StorageBackend | None = None,
) -> dict[str, Any]:
    """Execute a test run using the LLM agent + in-process Playwright.

    Args:
        run_detail: Full test run detail from the BE internal API, including
                    ``llm_config`` populated by the internal endpoint.
        storage:    Storage backend for uploading video and trace files.
                    Pass ``None`` to skip upload (e.g. in unit tests).

    Returns:
        Dict matching the TestRunResultUpdate schema:
        {status, step_results, recording_url, trace_url, error, started_at, completed_at}
    """
    started_at = datetime.now(timezone.utc)
    run_id: str = str(run_detail.get("id", "unknown"))

    # ── Validate LLM config ───────────────────────────────────────────────────
    llm_config = run_detail.get("llm_config")
    if not llm_config:
        return _make_failure_result(
            "No active LLM configured for this organisation", started_at
        )

    if not llm_config.get("model_name"):
        return _make_failure_result(
            "Active LLM has no model_name set — update the LLM record before running tests",
            started_at,
        )

    llm = create_adapter(
        provider=LLMProvider(llm_config["provider"]),
        api_key=llm_config["api_key"],
        model_name=llm_config["model_name"],
    )

    # ── Flatten steps ─────────────────────────────────────────────────────────
    payload = run_detail.get("test_case_payload") or {}
    raw_steps: list[dict[str, Any]] = payload.get("steps", [])

    flat_steps: list[tuple[str, str, str | None]] = []  # (action, description, group_name)
    for item in raw_steps:
        if item.get("type") == "group":
            group_name = item.get("name")
            for sub in item.get("steps", []):
                flat_steps.append((sub["action"], sub["description"], group_name))
        else:
            flat_steps.append((item["action"], item["description"], None))

    # ── Run agent loop with in-process Playwright ─────────────────────────────
    step_results: list[dict[str, Any]] = []
    overall_status = "passed"
    fatal_error: str | None = None
    recording_url: str | None = None
    trace_url: str | None = None

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as output_dir:
        service = PlaywrightService(
            output_dir=Path(output_dir),
            config=settings.browser_config,
        )
        try:
            logger.info("Starting agentic executor for run %s", run_id)
            await service.start()
            recording_start = time.monotonic()

            for i, (action, description, group_name) in enumerate(flat_steps):
                step_start = time.monotonic()
                result = await run_step(service, llm, action, description)
                duration_ms = int((time.monotonic() - step_start) * 1000)

                if result["status"] == "failed":
                    overall_status = "failed"

                step_results.append({
                    "index": i,
                    "action": action,
                    "group": group_name,
                    "description": description,
                    "status": result["status"],
                    "duration_ms": duration_ms,
                    "started_at_seconds": round(step_start - recording_start, 3),
                    "logs": [
                        f"{tc['name']}({tc['args']}) → {tc['result']}"
                        for tc in result.get("tool_calls_made", [])
                    ],
                    "screenshot_path": None,
                    "error": result.get("error"),
                })

        except Exception as exc:
            logger.exception("Executor crashed for run %s: %s", run_id, exc)
            fatal_error = str(exc)
            overall_status = "failed"

        finally:
            # stop() closes the context, finalizing video + trace before we read them
            await service.stop()

        if storage is not None:
            video_path = _find_file(Path(output_dir), "**/*.webm")
            if video_path:
                recording_url = await storage.upload(video_path, f"{run_id}-video.webm")
                logger.info("Video uploaded: %s", recording_url)
            else:
                logger.warning("No video file found in %s after run", output_dir)

            zip_path = _find_file(Path(output_dir), "**/*.zip")
            if zip_path:
                trace_url = await storage.upload(zip_path, f"{run_id}-trace.zip")
                logger.info("Trace uploaded: %s", trace_url)
            else:
                logger.warning("No trace file found in %s after run", output_dir)

    return {
        "status": overall_status,
        "step_results": step_results,
        "recording_url": recording_url,
        "trace_url": trace_url,
        "error": fatal_error,
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def _find_file(directory: Path, pattern: str) -> Path | None:
    """Return the first file matching *pattern* in *directory*, or None."""
    matches = sorted(directory.glob(pattern))
    if not matches:
        return None
    if len(matches) > 1:
        logger.warning("Multiple %s files found; using %s", pattern, matches[0])
    return matches[0]
