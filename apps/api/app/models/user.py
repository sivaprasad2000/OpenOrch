
from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, String, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TableNameMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user_organization import UserOrganization


class User(Base, TimestampMixin, TableNameMixin):

    __tablename__ = "users"  # type: ignore[assignment]

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active_organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )

    user_organizations: Mapped[list["UserOrganization"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    active_organization: Mapped["Organization | None"] = relationship(
        foreign_keys=[active_organization_id], lazy="selectin"
    )

    @staticmethod
    def generate_id_from_email(email: str) -> str:
        return hashlib.sha256(email.lower().encode()).hexdigest()

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, name={self.name})>"


@event.listens_for(User, "before_insert")
def receive_before_insert(mapper: Any, connection: Any, target: User) -> None:
    if not target.id:
        target.id = User.generate_id_from_email(target.email)
