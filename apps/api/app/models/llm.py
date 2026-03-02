
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TableNameMixin, TimestampMixin
from shared.llm.types import LLMProvider

if TYPE_CHECKING:
    from app.models.organization import Organization


class LLM(Base, TimestampMixin, TableNameMixin):

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[LLMProvider] = mapped_column(
        Enum(LLMProvider, native_enum=False, length=20), nullable=False
    )
    api_key: Mapped[str] = mapped_column(String(500), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")

    organization: Mapped["Organization"] = relationship(
        foreign_keys=[organization_id], lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<LLM(id={self.id}, name={self.name}, org={self.organization_id})>"
