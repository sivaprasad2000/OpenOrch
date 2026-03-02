
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    parent_team_id: Optional[str] = None


class TeamUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    parent_team_id: Optional[str] = None


class TeamResponse(BaseModel):
    id: str
    organization_id: str
    parent_team_id: Optional[str] = None
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeamInfo(BaseModel):
    id: str
    name: str
    parent_team_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
