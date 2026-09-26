from sqlalchemy import CheckConstraint, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, str_enum
from app.models.enums import ResourceProvider, ResourceType
from app.models.types import StringArray


class StudyResource(IdMixin, TimestampMixin, Base):
    """An external learning resource (Coursera, Udemy, NetAcad, ...). Linked to, never hosted."""

    __tablename__ = "study_resources"
    __table_args__ = (CheckConstraint("estimated_hours > 0", name="estimated_hours_positive"),)

    type: Mapped[ResourceType] = mapped_column(str_enum(ResourceType, "resource_type"))
    provider: Mapped[ResourceProvider] = mapped_column(
        str_enum(ResourceProvider, "resource_provider")
    )
    title: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(2048))
    estimated_hours: Mapped[float] = mapped_column(Numeric(5, 1, asdecimal=False))
    skill_tags: Mapped[list[str]] = mapped_column(StringArray, default=list)
