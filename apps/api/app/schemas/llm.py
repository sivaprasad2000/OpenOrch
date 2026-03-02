
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from shared.llm.types import LLMProvider


class LLMCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    provider: LLMProvider
    api_key: str = Field(..., min_length=1, max_length=500)
    model_name: str = Field(..., min_length=1, max_length=255)


class LLMUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    api_key: str | None = Field(None, min_length=1, max_length=500)
    model_name: str | None = Field(None, min_length=1, max_length=255)


class LLMResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    provider: LLMProvider
    model_name: str
    is_active: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
