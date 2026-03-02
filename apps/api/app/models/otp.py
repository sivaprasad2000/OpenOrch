
from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class OTP(Base, TimestampMixin):

    __tablename__ = "otps"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    @staticmethod
    def generate_expiry(minutes: int = 10) -> datetime:
        return datetime.now(timezone.utc) + timedelta(minutes=minutes)

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    def is_valid(self) -> bool:
        return not self.is_expired() and not self.is_used

    def __repr__(self) -> str:
        return f"<OTP(user_id={self.user_id}, code={self.code}, expires_at={self.expires_at})>"
