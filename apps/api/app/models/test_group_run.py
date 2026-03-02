from __future__ import annotations

import enum
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TableNameMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.test_group import TestGroup
    from app.models.test_run import TestRun


class GroupRunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"


class BrowserType(str, enum.Enum):
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class TestGroupRun(Base, TimestampMixin, TableNameMixin):
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )
    test_group_id: Mapped[str | None] = mapped_column(
        ForeignKey("test_group.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[GroupRunStatus] = mapped_column(
        Enum(GroupRunStatus, native_enum=False, length=20),
        nullable=False,
        default=GroupRunStatus.QUEUED,
    )
    browser: Mapped[BrowserType] = mapped_column(
        Enum(BrowserType, native_enum=False, length=20),
        nullable=False,
        default=BrowserType.CHROMIUM,
    )
    base_url_override: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    viewport_width: Mapped[int] = mapped_column(Integer, nullable=False, default=1280)
    viewport_height: Mapped[int] = mapped_column(Integer, nullable=False, default=720)

    test_group: Mapped[TestGroup | None] = relationship(lazy="selectin")
    test_runs: Mapped[list[TestRun]] = relationship(
        back_populates="test_group_run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TestGroupRun(id={self.id}, status={self.status})>"
