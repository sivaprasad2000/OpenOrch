
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StepAction(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    HOVER = "hover"
    WAIT = "wait"
    ASSERT = "assert"


class Step(BaseModel):
    action: StepAction
    description: str


class StepGroup(BaseModel):
    type: Literal["group"]
    name: str
    steps: list[Step]


class TestCasePayload(BaseModel):
    """Internal schema used to parse and validate steps during test execution."""

    steps: list[Union[StepGroup, Step]] = Field(default_factory=list)


def _validate_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Parse payload through TestCasePayload to enforce StepAction on every step."""
    TestCasePayload.model_validate(value)
    return value


class TestCaseCreate(BaseModel):
    payload: dict[str, Any]

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_payload(value)


class TestCaseUpdate(BaseModel):
    payload: dict[str, Any]

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_payload(value)


class TestCaseResponse(BaseModel):
    id: str
    test_group_id: str
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
