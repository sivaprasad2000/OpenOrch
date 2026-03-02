
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.test_group_run import BrowserType
from app.models.test_run import RunStatus


class RunConfig(BaseModel):

    browser: BrowserType = BrowserType.CHROMIUM
    base_url_override: str | None = Field(None, max_length=2048)
    viewport_width: int = Field(1280, gt=0)
    viewport_height: int = Field(720, gt=0)


class LLMConfig(BaseModel):
    """Internal-only: LLM configuration needed by the consumer to drive the agent."""

    provider: str
    api_key: str
    model_name: str


class StepResult(BaseModel):

    index: int
    action: str
    group: str | None = None
    description: str
    status: str
    duration_ms: int
    started_at_seconds: float = 0.0
    logs: list[str]
    screenshot_path: str | None = None
    error: str | None = None


class TestRunResultUpdate(BaseModel):

    status: RunStatus
    step_results: list[StepResult]
    recording_url: str | None = None
    trace_url: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class TestRunResponse(BaseModel):

    id: str
    test_case_id: str | None
    test_group_run_id: str | None
    status: RunStatus
    browser: BrowserType
    base_url_override: str | None
    viewport_width: int
    viewport_height: int
    step_results: list[dict[str, Any]] | None
    recording_url: str | None
    trace_url: str | None
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StepMarker(BaseModel):
    """Lightweight step data for seek bar markers — no tool call logs."""

    index: int
    action: str
    group: str | None = None
    description: str
    status: str
    started_at_seconds: float
    duration_ms: int
    error: str | None = None


class PlayerResponse(BaseModel):
    """Response for the player endpoint: recording URL + seek bar markers."""

    recording_url: str | None
    markers: list[StepMarker]


class TestRunDetailResponse(BaseModel):

    id: str
    test_case_id: str | None
    test_group_run_id: str | None
    status: RunStatus
    browser: BrowserType
    base_url_override: str | None
    viewport_width: int
    viewport_height: int
    test_case_payload: dict[str, Any] | None
    llm_config: LLMConfig | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
