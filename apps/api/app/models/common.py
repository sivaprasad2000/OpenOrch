from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    environment: str


class ErrorResponse(BaseModel):
    detail: str
    error_code: str | None = None


class MessageResponse(BaseModel):
    message: str
