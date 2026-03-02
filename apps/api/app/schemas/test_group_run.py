from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.test_group_run import BrowserType, GroupRunStatus
from app.schemas.test_run import TestRunResponse


class TestGroupRunResponse(BaseModel):
    id: str
    test_group_id: str | None
    status: GroupRunStatus
    browser: BrowserType
    base_url_override: str | None
    viewport_width: int
    viewport_height: int
    test_runs: list[TestRunResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
