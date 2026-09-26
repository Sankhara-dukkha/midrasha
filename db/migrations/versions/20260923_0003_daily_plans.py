"""daily_plans: one row per (user, date) makes planning a day atomic

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_daily_plans_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_plans")),
        sa.UniqueConstraint("user_id", "plan_date", name="uq_daily_plans_user_date"),
    )
    # Every day that already has missions was planned; record it so it is never re-planned.
    # gen_random_uuid() is built in from PostgreSQL 13.
    op.execute(
        "INSERT INTO daily_plans (id, user_id, plan_date) "
        "SELECT gen_random_uuid(), user_id, scheduled_date "
        "FROM (SELECT DISTINCT user_id, scheduled_date FROM mission_instances) AS planned"
    )


def downgrade() -> None:
    op.drop_table("daily_plans")
