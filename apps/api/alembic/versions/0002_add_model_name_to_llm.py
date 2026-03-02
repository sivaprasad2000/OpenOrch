"""Add model_name to llm

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "llm",
        sa.Column("model_name", sa.String(255), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("llm", "model_name")
