from enum import StrEnum


class Track(StrEnum):
    CYBER = "cyber"
    OSINT = "osint"
    JOURNALIST = "journalist"
    GENERAL = "general"


class ResourceType(StrEnum):
    VIDEO = "video"
    COURSE = "course"
    BOOK = "book"
    ARTICLE = "article"


class ResourceProvider(StrEnum):
    COURSERA = "Coursera"
    UDEMY = "Udemy"
    NETACAD = "NetAcad"
    OTHER = "Other"


class MissionType(StrEnum):
    LANGUAGE = "language"
    FITNESS = "fitness"
    STUDY = "study"
    OSINT = "osint"
    SCENARIO = "scenario"


class Phase(StrEnum):
    INDUCTION = "induction"  # days 1-21
    SPECIALISATION = "specialisation"  # days 22-60
    OPERATIONS = "operations"  # days 61-90


class MissionStatus(StrEnum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
