import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models.enums import (
    MissionStatus,
    MissionType,
    Phase,
    ResourceProvider,
    ResourceType,
)

SkillTag = str  # e.g. "cyber_basics", "osint_social", "hebrew_alphabet"


class StudyResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: ResourceType
    provider: ResourceProvider
    title: str
    url: HttpUrl
    estimated_hours: float
    skill_tags: list[SkillTag]


class MissionTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    type: MissionType
    skill_tags: list[SkillTag]
    day_offset: int | None = Field(default=None, ge=1, le=90)
    phase: Phase | None = None
    difficulty: int = Field(ge=1, le=5)
    required_resource_ids: list[uuid.UUID]


class MissionInstanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mission_template_id: uuid.UUID
    scheduled_date: date
    status: MissionStatus
    template: MissionTemplateRead


class MissionLogCreate(BaseModel):
    start_time: datetime
    end_time: datetime | None = None
    notes: str | None = Field(default=None, max_length=5000)
    metrics: dict[str, float | int | str | bool] = Field(default_factory=dict)


class MissionLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mission_instance_id: uuid.UUID
    start_time: datetime
    end_time: datetime | None
    notes: str | None
    recruiter_score: int | None = Field(default=None, ge=0, le=100)
    metrics: dict
