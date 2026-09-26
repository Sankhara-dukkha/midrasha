"""Idempotent loader for the seed catalogue (db/seeds/catalog.json).

Rows get stable ids derived from their catalogue key, so re-running updates in place.
"""

import uuid
from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models import MissionTemplate, StudyResource, User
from app.models.enums import MissionType, Phase, ResourceProvider, ResourceType, Track
from app.services.planner import PlayerHistory, select_templates

_NAMESPACE = uuid.UUID("5b0c1f7e-3d7a-4f52-9a61-0d4a6f1c2e90")


class CatalogError(ValueError):
    """The catalogue is inconsistent; nothing has been written."""


def catalog_id(kind: str, key: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, f"{kind}:{key}")


def _upsert(db: Session, model: type, row_id: uuid.UUID, **values: Any) -> Any:
    row = db.get(model, row_id)
    if row is None:
        row = model(id=row_id)
        db.add(row)
    for name, value in values.items():
        setattr(row, name, value)
    return row


def _check_pinned(templates: list[dict[str, Any]]) -> None:
    """Fail if a day-pinned template could never be scheduled on its day.

    Pinned templates outrank everything else in their slot, so it is enough to run the planner
    with only the pinned templates for each day: any it leaves out would be silently dropped
    (two pinned for one slot, or no slot for the type in that phase).
    """
    by_day: dict[int, list[MissionTemplate]] = defaultdict(list)
    for t in templates:
        if t.get("day_offset") is not None:
            by_day[t["day_offset"]].append(
                MissionTemplate(
                    id=catalog_id("template", t["key"]),
                    name=t["name"],
                    type=MissionType(t["type"]),
                    day_offset=t["day_offset"],
                    difficulty=t["difficulty"],
                    skill_tags=t["skill_tags"],
                )
            )
    recruit = User(
        track=Track.GENERAL,
        language_level_hebrew=0,
        language_level_arabic=0,
        language_level_farsi=0,
    )
    for day, pinned in sorted(by_day.items()):
        try:
            chosen = select_templates(recruit, day, pinned, PlayerHistory(), on_date=date.min)
        except ValueError as exc:
            raise CatalogError(str(exc)) from exc
        dropped = sorted(t.name for t in pinned if t not in chosen)
        if dropped:
            raise CatalogError(f"pinned template(s) {dropped} cannot be scheduled on day {day}")


def load_catalog(db: Session, catalog: dict[str, Any]) -> None:
    """Upsert the catalogue. Validates first, so a rejected catalogue writes nothing."""
    _check_pinned(catalog["templates"])
    resources: dict[str, StudyResource] = {}
    for r in catalog["resources"]:
        resources[r["key"]] = _upsert(
            db,
            StudyResource,
            catalog_id("resource", r["key"]),
            type=ResourceType(r["type"]),
            provider=ResourceProvider(r["provider"]),
            title=r["title"],
            url=r["url"],
            estimated_hours=r["estimated_hours"],
            skill_tags=r["skill_tags"],
        )
    for t in catalog["templates"]:
        _upsert(
            db,
            MissionTemplate,
            catalog_id("template", t["key"]),
            name=t["name"],
            description=t["description"],
            type=MissionType(t["type"]),
            phase=Phase(t["phase"]) if t.get("phase") else None,
            day_offset=t.get("day_offset"),
            difficulty=t["difficulty"],
            skill_tags=t["skill_tags"],
            required_resources=[resources[key] for key in t.get("resources", [])],
        )
    db.commit()
