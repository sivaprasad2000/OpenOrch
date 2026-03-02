from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.test_group import TestGroupStatus


class TestGroupBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    base_url: str | None = Field(None, max_length=2048)
    tags: list[str] | None = None


class TestGroupCreate(TestGroupBase):
    pass


class TestGroupUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    base_url: str | None = Field(None, max_length=2048)
    status: TestGroupStatus | None = None
    tags: list[str] | None = None


class TestGroupResponse(TestGroupBase):
    id: str
    status: TestGroupStatus
    organization_id: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
