import uuid
from datetime import date
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import BCRYPT_MAX_BYTES
from app.models.enums import Track


def _validate_time_zone(value: str) -> str:
    if value not in available_timezones():
        raise ValueError("unknown IANA time zone")
    return value


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10)
    display_name: str = Field(min_length=1, max_length=80)
    time_zone: str = "UTC"
    track: Track = Track.GENERAL

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, v: str) -> str:
        if len(v.encode()) > BCRYPT_MAX_BYTES:
            raise ValueError(f"password must be at most {BCRYPT_MAX_BYTES} bytes")
        return v

    @field_validator("time_zone")
    @classmethod
    def valid_tz(cls, v: str) -> str:
        return _validate_time_zone(v)


class UserUpdate(BaseModel):
    """Fields the player may change from /settings. All optional (PATCH semantics)."""

    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    time_zone: str | None = None
    track: Track | None = None
    language_level_hebrew: int | None = Field(default=None, ge=0, le=5)
    language_level_arabic: int | None = Field(default=None, ge=0, le=5)
    language_level_farsi: int | None = Field(default=None, ge=0, le=5)
    fitness_target_hr_zone: int | None = Field(default=None, ge=1, le=5)
    fitness_daily_kcal_goal: int | None = Field(default=None, ge=0, le=5000)

    @field_validator("time_zone")
    @classmethod
    def valid_tz(cls, v: str | None) -> str | None:
        return None if v is None else _validate_time_zone(v)


class UserRead(BaseModel):
    """Public view of a user. Never includes password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    time_zone: str
    track: Track
    language_level_hebrew: int
    language_level_arabic: int
    language_level_farsi: int
    fitness_target_hr_zone: int
    fitness_daily_kcal_goal: int
    program_start_date: date
