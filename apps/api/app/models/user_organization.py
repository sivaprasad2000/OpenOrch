from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TableNameMixin, TimestampMixin


class OrgRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class UserOrganization(Base, TimestampMixin, TableNameMixin):
    __table_args__ = (UniqueConstraint("user_id", "organization_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[OrgRole] = mapped_column(
        Enum(OrgRole, native_enum=False, length=20), default=OrgRole.MEMBER, nullable=False
    )

    user: Mapped[User] = relationship(back_populates="user_organizations")
    organization: Mapped[Organization] = relationship(back_populates="user_organizations")

    def __repr__(self) -> str:
        return (
            f"<UserOrganization(user_id={self.user_id}, "
            f"organization_id={self.organization_id}, role={self.role})>"
        )
