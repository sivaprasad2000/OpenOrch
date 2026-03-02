from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user_organization import OrgRole


class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class OrganizationResponse(OrganizationBase):
    id: str
    active_llm_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SetActiveLLMRequest(BaseModel):
    llm_id: str | None = None


class AssignRoleRequest(BaseModel):
    user_id: str
    role: OrgRole
