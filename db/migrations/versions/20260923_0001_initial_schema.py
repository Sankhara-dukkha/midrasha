"""initial schema: users, study resources, mission templates/instances/logs

Revision ID: 0001
Revises:
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("time_zone", sa.String(64), nullable=False),
        sa.Column("language_level_hebrew", sa.SmallInteger(), nullable=False),
        sa.Column("language_level_arabic", sa.SmallInteger(), nullable=False),
        sa.Column("language_level_farsi", sa.SmallInteger(), nullable=False),
        sa.Column("fitness_target_hr_zone", sa.SmallInteger(), nullable=False),
        sa.Column("fitness_daily_kcal_goal", sa.Integer(), nullable=False),
        sa.Column("track", sa.String(32), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.CheckConstraint(
            "language_level_hebrew BETWEEN 0 AND 5", name=op.f("ck_users_hebrew_level_range")
        ),
        sa.CheckConstraint(
            "language_level_arabic BETWEEN 0 AND 5", name=op.f("ck_users_arabic_level_range")
        ),
        sa.CheckConstraint(
            "language_level_farsi BETWEEN 0 AND 5", name=op.f("ck_users_farsi_level_range")
        ),
        sa.CheckConstraint(
            "fitness_target_hr_zone BETWEEN 1 AND 5", name=op.f("ck_users_hr_zone_range")
        ),
        sa.CheckConstraint(
            "fitness_daily_kcal_goal >= 0", name=op.f("ck_users_kcal_goal_non_negative")
        ),
        sa.CheckConstraint(
            _in("track", ["cyber", "osint", "journalist", "general"]), name=op.f("ck_users_track")
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "study_resources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("estimated_hours", sa.Numeric(5, 1), nullable=False),
        sa.Column("skill_tags", postgresql.ARRAY(sa.String(64)), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_study_resources")),
        sa.CheckConstraint(
            "estimated_hours > 0", name=op.f("ck_study_resources_estimated_hours_positive")
        ),
        sa.CheckConstraint(
            _in("type", ["video", "course", "book", "article"]),
            name=op.f("ck_study_resources_resource_type"),
        ),
        sa.CheckConstraint(
            _in("provider", ["Coursera", "Udemy", "NetAcad", "Other"]),
            name=op.f("ck_study_resources_resource_provider"),
        ),
    )

    op.create_table(
        "mission_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("skill_tags", postgresql.ARRAY(sa.String(64)), nullable=False),
        sa.Column("day_offset", sa.SmallInteger(), nullable=True),
        sa.Column("phase", sa.String(32), nullable=True),
        sa.Column("difficulty", sa.SmallInteger(), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mission_templates")),
        sa.CheckConstraint(
            "day_offset IS NULL OR day_offset BETWEEN 1 AND 90",
            name=op.f("ck_mission_templates_day_offset_range"),
        ),
        sa.CheckConstraint(
            "day_offset IS NOT NULL OR phase IS NOT NULL",
            name=op.f("ck_mission_templates_day_or_phase"),
        ),
        sa.CheckConstraint(
            "difficulty BETWEEN 1 AND 5", name=op.f("ck_mission_templates_difficulty_range")
        ),
        sa.CheckConstraint(
            _in("type", ["language", "fitness", "study", "osint", "scenario"]),
            name=op.f("ck_mission_templates_mission_type"),
        ),
        sa.CheckConstraint(
            _in("phase", ["induction", "specialisation", "operations"]),
            name=op.f("ck_mission_templates_phase"),
        ),
    )

    op.create_table(
        "mission_template_resources",
        sa.Column("mission_template_id", sa.Uuid(), nullable=False),
        sa.Column("study_resource_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint(
            "mission_template_id", "study_resource_id", name=op.f("pk_mission_template_resources")
        ),
        sa.ForeignKeyConstraint(
            ["mission_template_id"],
            ["mission_templates.id"],
            ondelete="CASCADE",
            name=op.f("fk_mission_template_resources_template_id"),
        ),
        sa.ForeignKeyConstraint(
            ["study_resource_id"],
            ["study_resources.id"],
            ondelete="RESTRICT",
            name=op.f("fk_mission_template_resources_resource_id"),
        ),
    )

    op.create_table(
        "mission_instances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("mission_template_id", sa.Uuid(), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mission_instances")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name=op.f("fk_mission_instances_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["mission_template_id"],
            ["mission_templates.id"],
            ondelete="RESTRICT",
            name=op.f("fk_mission_instances_mission_template_id_mission_templates"),
        ),
        sa.UniqueConstraint(
            "user_id",
            "mission_template_id",
            "scheduled_date",
            name=op.f("uq_mission_instance_per_day"),
        ),
        sa.CheckConstraint(
            _in("status", ["assigned", "in_progress", "completed", "failed"]),
            name=op.f("ck_mission_instances_mission_status"),
        ),
    )
    op.create_index(
        "ix_mission_instances_user_date", "mission_instances", ["user_id", "scheduled_date"]
    )

    op.create_table(
        "mission_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mission_instance_id", sa.Uuid(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recruiter_score", sa.SmallInteger(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mission_logs")),
        sa.ForeignKeyConstraint(
            ["mission_instance_id"],
            ["mission_instances.id"],
            ondelete="CASCADE",
            name=op.f("fk_mission_logs_mission_instance_id_mission_instances"),
        ),
        sa.CheckConstraint(
            "recruiter_score IS NULL OR recruiter_score BETWEEN 0 AND 100",
            name=op.f("ck_mission_logs_score_range"),
        ),
        sa.CheckConstraint(
            "end_time IS NULL OR end_time >= start_time",
            name=op.f("ck_mission_logs_end_after_start"),
        ),
    )
    op.create_index("ix_mission_logs_mission_instance_id", "mission_logs", ["mission_instance_id"])


def downgrade() -> None:
    op.drop_table("mission_logs")
    op.drop_table("mission_instances")
    op.drop_table("mission_template_resources")
    op.drop_table("mission_templates")
    op.drop_table("study_resources")
    op.drop_table("users")
