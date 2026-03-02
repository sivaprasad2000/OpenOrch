from __future__ import annotations

from datetime import datetime
import enum
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TableNameMixin, TimestampMixin
from app.models.test_group_run import BrowserType
from app.models.types import _JSONBCompat

if TYPE_CHECKING:
    from app.models.test_case import TestCase
    from app.models.test_group_run import TestGroupRun


class RunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"


class TestRun(Base, TimestampMixin, TableNameMixin):
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )
    test_case_id: Mapped[str | None] = mapped_column(
        ForeignKey("test_case.id", ondelete="SET NULL"), nullable=True, index=True
    )
    test_group_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("test_group_run.id", ondelete="CASCADE"), nullable=True, index=True
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, native_enum=False, length=20),
        nullable=False,
        default=RunStatus.QUEUED,
    )
    browser: Mapped[BrowserType] = mapped_column(
        Enum(BrowserType, native_enum=False, length=20),
        nullable=False,
        default=BrowserType.CHROMIUM,
    )
    base_url_override: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    viewport_width: Mapped[int] = mapped_column(Integer, nullable=False, default=1280)
    viewport_height: Mapped[int] = mapped_column(Integer, nullable=False, default=720)
    step_results: Mapped[list[dict[str, Any]] | None] = mapped_column(_JSONBCompat, nullable=True)
    recording_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    trace_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    test_case: Mapped[TestCase | None] = relationship(lazy="selectin")
    test_group_run: Mapped[TestGroupRun | None] = relationship(
        back_populates="test_runs", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<TestRun(id={self.id}, status={self.status})>"
