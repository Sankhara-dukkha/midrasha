import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, str_enum
from app.models.enums import MissionStatus, MissionType, Phase
from app.models.study_resource import StudyResource
from app.models.types import JsonDict, StringArray

# MissionTemplate.required_resource_ids is modelled as a join table so every id is a real FK.
mission_template_resources = Table(
    "mission_template_resources",
    Base.metadata,
    Column(
        "mission_template_id",
        ForeignKey(
            "mission_templates.id",
            ondelete="CASCADE",
            name="fk_mission_template_resources_template_id",  # default name exceeds 63 chars
        ),
        primary_key=True,
    ),
    Column(
        "study_resource_id",
        ForeignKey(
            "study_resources.id",
            ondelete="RESTRICT",
            name="fk_mission_template_resources_resource_id",
        ),
        primary_key=True,
    ),
)


class MissionTemplate(IdMixin, TimestampMixin, Base):
    """A reusable mission definition. Scheduled either on a specific program day or by phase."""

    __tablename__ = "mission_templates"
    __table_args__ = (
        CheckConstraint(
            "day_offset IS NULL OR day_offset BETWEEN 1 AND 90", name="day_offset_range"
        ),
        CheckConstraint("day_offset IS NOT NULL OR phase IS NOT NULL", name="day_or_phase"),
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="difficulty_range"),
    )

    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    type: Mapped[MissionType] = mapped_column(str_enum(MissionType, "mission_type"))
    skill_tags: Mapped[list[str]] = mapped_column(StringArray, default=list)
    day_offset: Mapped[int | None] = mapped_column(SmallInteger)
    phase: Mapped[Phase | None] = mapped_column(str_enum(Phase, "phase"))
    difficulty: Mapped[int] = mapped_column(SmallInteger, default=1)

    required_resources: Mapped[list[StudyResource]] = relationship(
        secondary=mission_template_resources, lazy="selectin"
    )

    @property
    def required_resource_ids(self) -> list[uuid.UUID]:
        return [r.id for r in self.required_resources]


class MissionInstance(IdMixin, TimestampMixin, Base):
    """A template assigned to one user on one date."""

    __tablename__ = "mission_instances"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "mission_template_id", "scheduled_date", name="uq_mission_instance_per_day"
        ),
        Index("ix_mission_instances_user_date", "user_id", "scheduled_date"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    mission_template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mission_templates.id", ondelete="RESTRICT")
    )
    scheduled_date: Mapped[date] = mapped_column(Date)
    status: Mapped[MissionStatus] = mapped_column(
        str_enum(MissionStatus, "mission_status"), default=MissionStatus.ASSIGNED
    )

    user: Mapped["User"] = relationship(back_populates="mission_instances")  # noqa: F821
    template: Mapped[MissionTemplate] = relationship(lazy="joined")
    logs: Mapped[list["MissionLog"]] = relationship(
        back_populates="mission_instance", cascade="all, delete-orphan"
    )


class DailyPlan(IdMixin, TimestampMixin, Base):
    """Marks one user's date as planned. The unique key is what makes planning a day atomic.

    `uq_mission_instance_per_day` only rejects the same template twice, so two concurrent requests
    that chose different templates (e.g. settings changed in between) could both insert. Only one
    of them can insert this row.
    """

    __tablename__ = "daily_plans"
    __table_args__ = (UniqueConstraint("user_id", "plan_date", name="uq_daily_plans_user_date"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    plan_date: Mapped[date] = mapped_column(Date)


class MissionLog(IdMixin, TimestampMixin, Base):
    """One attempt/session at a mission, with player notes and measured metrics."""

    __tablename__ = "mission_logs"
    __table_args__ = (
        CheckConstraint(
            "recruiter_score IS NULL OR recruiter_score BETWEEN 0 AND 100", name="score_range"
        ),
        CheckConstraint("end_time IS NULL OR end_time >= start_time", name="end_after_start"),
    )

    mission_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mission_instances.id", ondelete="CASCADE"), index=True
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    recruiter_score: Mapped[int | None] = mapped_column(SmallInteger)
    # Free-form measurements, e.g. {"avg_hr": 142, "kcal": 310, "vocab_correct": 8}.
    metrics: Mapped[dict] = mapped_column(JsonDict, default=dict)

    mission_instance: Mapped[MissionInstance] = relationship(back_populates="logs")
