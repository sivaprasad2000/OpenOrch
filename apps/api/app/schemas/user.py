
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, max_length=100)


class UserResponse(UserBase):
    id: str
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserOrganizationInfo(BaseModel):
    id: str
    name: str
    role: str
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActiveOrganizationInfo(BaseModel):
    id: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class UserMeResponse(UserBase):
    id: str
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    active_organization: Optional[ActiveOrganizationInfo] = None
    organizations: list[UserOrganizationInfo] = []

    model_config = ConfigDict(from_attributes=True)


class SetActiveOrganizationRequest(BaseModel):
    organization_id: str


class UserInDB(UserResponse):
    password: str


class UserVerifyEmail(BaseModel):
    email: EmailStr
    verification_token: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)
