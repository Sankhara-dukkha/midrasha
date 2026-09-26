from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import MissionInstance, MissionLog, MissionTemplate, StudyResource, User
from app.models.enums import MissionType, Phase, ResourceProvider, ResourceType


def _template(**overrides) -> MissionTemplate:
    fields = dict(
        name="Alphabet I",
        description="Learn the first five Hebrew letters.",
        type=MissionType.LANGUAGE,
        skill_tags=["hebrew_alphabet"],
        day_offset=1,
        difficulty=1,
    )
    return MissionTemplate(**(fields | overrides))


def _me(db: Session) -> User:
    return db.scalar(select(User).where(User.email == "recruit@example.com"))


def test_missions_empty_for_new_user(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.get("/api/missions", params={"date": "today"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.parametrize("bad", ["yesterday", "2026-13-01", "2026-02-30", "2026-01-011", ""])
def test_missions_rejects_bad_date(
    client: TestClient, auth_headers: dict[str, str], bad: str
) -> None:
    resp = client.get("/api/missions", params={"date": bad}, headers=auth_headers)
    assert resp.status_code == 422


def test_missions_list_and_detail(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    resource = StudyResource(
        type=ResourceType.COURSE,
        provider=ResourceProvider.NETACAD,
        title="Introduction to Cybersecurity",
        url="https://www.netacad.com/courses/introduction-to-cybersecurity",
        estimated_hours=6,
        skill_tags=["cyber_basics"],
    )
    template = _template(type=MissionType.STUDY, required_resources=[resource])
    db_session.add(template)
    db_session.flush()
    mission = MissionInstance(
        user_id=_me(db_session).id, mission_template_id=template.id, scheduled_date=date(2026, 1, 5)
    )
    db_session.add(mission)
    db_session.commit()

    listed = client.get("/api/missions", params={"date": "2026-01-05"}, headers=auth_headers).json()
    assert len(listed) == 1
    assert listed[0]["status"] == "assigned"
    assert listed[0]["template"]["required_resource_ids"] == [str(resource.id)]

    detail = client.get(f"/api/missions/{mission.id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["template"]["name"] == "Alphabet I"


def test_cannot_read_other_users_mission(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    other = User(email="other@example.com", password_hash="x", display_name="Other")
    template = _template()
    db_session.add_all([other, template])
    db_session.flush()
    theirs = MissionInstance(
        user_id=other.id, mission_template_id=template.id, scheduled_date=date(2026, 1, 5)
    )
    db_session.add(theirs)
    db_session.commit()

    assert client.get(f"/api/missions/{theirs.id}", headers=auth_headers).status_code == 404


@pytest.mark.parametrize(
    "overrides",
    [
        {"difficulty": 6},
        {"day_offset": 91},
        {"day_offset": None, "phase": None},
    ],
)
def test_template_constraints(db_session: Session, overrides: dict) -> None:
    db_session.add(_template(**overrides))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_template_can_be_phase_scheduled(db_session: Session) -> None:
    db_session.add(_template(day_offset=None, phase=Phase.INDUCTION))
    db_session.commit()


def test_mission_log_score_range(db_session: Session, auth_headers: dict[str, str]) -> None:
    template = _template()
    db_session.add(template)
    db_session.flush()
    mission = MissionInstance(
        user_id=_me(db_session).id, mission_template_id=template.id, scheduled_date=date.today()
    )
    db_session.add(mission)
    db_session.flush()
    db_session.add(
        MissionLog(
            mission_instance_id=mission.id,
            start_time=datetime(2026, 1, 5, 8, tzinfo=UTC),
            recruiter_score=101,
            metrics={"vocab_correct": 8},
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
