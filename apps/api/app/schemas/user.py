from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8, max_length=100)


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
    active_organization: ActiveOrganizationInfo | None = None
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
