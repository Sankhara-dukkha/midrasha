"""Importing this package registers every model on Base.metadata (needed by Alembic)."""

from app.models.base import Base
from app.models.mission import (
    DailyPlan,
    MissionInstance,
    MissionLog,
    MissionTemplate,
    mission_template_resources,
)
from app.models.study_resource import StudyResource
from app.models.user import User

__all__ = [
    "Base",
    "DailyPlan",
    "MissionInstance",
    "MissionLog",
    "MissionTemplate",
    "StudyResource",
    "User",
    "mission_template_resources",
]
