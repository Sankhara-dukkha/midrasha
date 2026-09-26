from datetime import date

from sqlalchemy import CheckConstraint, Date, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, str_enum
from app.models.enums import Track


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("language_level_hebrew BETWEEN 0 AND 5", name="hebrew_level_range"),
        CheckConstraint("language_level_arabic BETWEEN 0 AND 5", name="arabic_level_range"),
        CheckConstraint("language_level_farsi BETWEEN 0 AND 5", name="farsi_level_range"),
        CheckConstraint("fitness_target_hr_zone BETWEEN 1 AND 5", name="hr_zone_range"),
        CheckConstraint("fitness_daily_kcal_goal >= 0", name="kcal_goal_non_negative"),
    )

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    time_zone: Mapped[str] = mapped_column(String(64), default="UTC")

    # Everyone starts at zero (see docs/PRD.md: zero-knowledge baseline).
    language_level_hebrew: Mapped[int] = mapped_column(SmallInteger, default=0)
    language_level_arabic: Mapped[int] = mapped_column(SmallInteger, default=0)
    language_level_farsi: Mapped[int] = mapped_column(SmallInteger, default=0)

    # Fitness baseline: target heart-rate zone (1-5) and daily active-calorie goal.
    fitness_target_hr_zone: Mapped[int] = mapped_column(SmallInteger, default=2)
    fitness_daily_kcal_goal: Mapped[int] = mapped_column(default=300)

    # Day 1 of the 90-day programme, in the player's local calendar (set at registration).
    program_start_date: Mapped[date] = mapped_column(Date, default=date.today)

    track: Mapped[Track] = mapped_column(str_enum(Track, "track"), default=Track.GENERAL)

    mission_instances: Mapped[list["MissionInstance"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
