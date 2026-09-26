"""users.program_start_date: day 1 of the player's 90-day programme

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add nullable, backfill existing players from their sign-up date, then enforce NOT NULL.
    op.add_column("users", sa.Column("program_start_date", sa.Date(), nullable=True))
    op.execute("UPDATE users SET program_start_date = CAST(created_at AS DATE)")
    op.alter_column("users", "program_start_date", nullable=False)


def downgrade() -> None:
    op.drop_column("users", "program_start_date")
