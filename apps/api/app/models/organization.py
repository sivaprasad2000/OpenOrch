from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TableNameMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user_organization import UserOrganization


class Organization(Base, TimestampMixin, TableNameMixin):
    __tablename__ = "organizations"  # type: ignore[assignment]

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    active_llm_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("llm.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )

    user_organizations: Mapped[list[UserOrganization]] = relationship(
        back_populates="organization", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name})>"
