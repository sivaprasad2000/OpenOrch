
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TableNameMixin, TimestampMixin
from app.models.types import _JSONBCompat

if TYPE_CHECKING:
    from app.models.test_group import TestGroup


class TestCase(Base, TimestampMixin, TableNameMixin):

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )
    test_group_id: Mapped[str] = mapped_column(
        ForeignKey("test_group.id", ondelete="CASCADE"), nullable=False, index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(_JSONBCompat, nullable=False)

    test_group: Mapped["TestGroup"] = relationship(lazy="selectin")

    def __repr__(self) -> str:
        return f"<TestCase(id={self.id}, test_group_id={self.test_group_id})>"
