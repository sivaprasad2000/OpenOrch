
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TableNameMixin, TimestampMixin
from app.models.types import _StringArrayCompat

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class TestGroupStatus(str, enum.Enum):

    ACTIVE = "active"
    ARCHIVED = "archived"


class TestGroup(Base, TimestampMixin, TableNameMixin):

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[TestGroupStatus] = mapped_column(
        Enum(TestGroupStatus, native_enum=False, length=20),
        nullable=False,
        default=TestGroupStatus.ACTIVE,
    )
    tags: Mapped[list[str] | None] = mapped_column(_StringArrayCompat, nullable=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    organization: Mapped["Organization"] = relationship(lazy="selectin")
    creator: Mapped["User | None"] = relationship(
        foreign_keys=[created_by], lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<TestGroup(id={self.id}, name={self.name}, org={self.organization_id})>"
