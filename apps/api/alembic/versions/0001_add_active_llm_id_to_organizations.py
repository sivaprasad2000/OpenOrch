"""Add active_llm_id to organizations

Revision ID: 0001
Revises:
Create Date: 2026-02-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("active_llm_id", sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_organizations_active_llm_id",
        "organizations",
        "llm",
        ["active_llm_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_organizations_active_llm_id", "organizations", type_="foreignkey")
    op.drop_column("organizations", "active_llm_id")
