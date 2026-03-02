from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    parent_team_id: str | None = None


class TeamUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    parent_team_id: str | None = None


class TeamResponse(BaseModel):
    id: str
    organization_id: str
    parent_team_id: str | None = None
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeamInfo(BaseModel):
    id: str
    name: str
    parent_team_id: str | None = None

    model_config = ConfigDict(from_attributes=True)
