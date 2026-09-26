import json
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import DailyPlan, MissionInstance, MissionTemplate, StudyResource, User
from app.models.enums import MissionStatus, MissionType
from app.services import planner
from app.services.catalog import CatalogError, load_catalog
from app.services.planner import ensure_missions, plan_daily_missions, program_day_for

CATALOG = json.loads(
    (Path(__file__).resolve().parents[2] / "db" / "seeds" / "catalog.json").read_text("utf-8")
)
CORE_TYPES = {MissionType.LANGUAGE, MissionType.FITNESS, MissionType.STUDY}


@pytest.fixture
def seeded(db_session: Session) -> Session:
    load_catalog(db_session, CATALOG)
    return db_session


def make_user(db: Session, start: date, **overrides) -> User:
    user = User(
        email=f"u{start.isoformat()}@example.com",
        password_hash="x",
        display_name="U",
        program_start_date=start,
        **overrides,
    )
    db.add(user)
    db.commit()
    return user


def count(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


# --- programme day ------------------------------------------------------------------------


def test_program_day_counts_from_start() -> None:
    user = User(program_start_date=date(2026, 3, 1))
    assert program_day_for(user, date(2026, 3, 1)) == 1
    assert program_day_for(user, date(2026, 3, 22)) == 22


def test_register_sets_start_date_in_players_time_zone(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "tz@example.com",
            "password": "correct-horse-battery",
            "display_name": "TZ",
            "time_zone": "Pacific/Kiritimati",  # UTC+14: often a different date from UTC
        },
    )
    expected = datetime.now(ZoneInfo("Pacific/Kiritimati")).date()
    assert resp.json()["program_start_date"] == expected.isoformat()


# --- seed catalogue -----------------------------------------------------------------------


def test_catalog_load_is_idempotent(db_session: Session) -> None:
    load_catalog(db_session, CATALOG)
    first = (count(db_session, MissionTemplate), count(db_session, StudyResource))
    load_catalog(db_session, CATALOG)
    assert (count(db_session, MissionTemplate), count(db_session, StudyResource)) == first
    assert first[0] > 0 and first[1] > 0


@pytest.mark.parametrize("day", [1, 2, 10, 21, 22, 40, 60, 61, 75, 90])
def test_catalog_covers_every_phase(seeded: Session, day: int) -> None:
    start = date(2026, 1, 1)
    user = make_user(seeded, start)
    missions = plan_daily_missions(seeded, user, day, start + timedelta(days=day - 1))
    assert 3 <= len(missions) <= 5
    assert CORE_TYPES <= {m.template.type for m in missions}


def test_every_pinned_template_is_scheduled_on_its_day(seeded: Session) -> None:
    start = date(2026, 1, 1)
    user = make_user(seeded, start)
    pinned = seeded.scalars(
        select(MissionTemplate).where(MissionTemplate.day_offset.is_not(None))
    ).all()
    assert pinned
    for t in pinned:
        day = start + timedelta(days=t.day_offset - 1)
        assert t in {m.template for m in plan_daily_missions(seeded, user, t.day_offset, day)}


def _pinned(key: str, type_: str, day: int) -> dict:
    return {
        "key": key,
        "name": key,
        "description": key,
        "type": type_,
        "day_offset": day,
        "difficulty": 1,
        "skill_tags": [],
    }


@pytest.mark.parametrize(
    "extra",
    [
        # The seed already pins a study mission (orientation) to day 1, which has one study slot.
        pytest.param([_pinned("clash", "study", 1)], id="slot-already-taken"),
        pytest.param(
            [_pinned("a", "fitness", 5), _pinned("b", "fitness", 5)], id="two-for-one-slot"
        ),
    ],
)
def test_catalog_rejects_pinned_templates_that_would_be_dropped(
    db_session: Session, extra: list[dict]
) -> None:
    bad = CATALOG | {"templates": [*CATALOG["templates"], *extra]}
    with pytest.raises(CatalogError, match="cannot be scheduled"):
        load_catalog(db_session, bad)
    # Validation runs before any upsert: a rejected catalogue writes nothing at all.
    assert count(db_session, MissionTemplate) == 0
    assert count(db_session, StudyResource) == 0


# --- persistence --------------------------------------------------------------------------


def test_ensure_missions_persists_once(seeded: Session) -> None:
    today = date(2026, 1, 1)
    user = make_user(seeded, today)
    first = ensure_missions(seeded, user, today)
    assert 3 <= len(first) <= 5
    assert all(m.status == MissionStatus.ASSIGNED for m in first)

    again = ensure_missions(seeded, user, today)
    assert {m.id for m in again} == {m.id for m in first}
    assert count(seeded, MissionInstance) == len(first)


def test_no_missions_after_day_90(seeded: Session) -> None:
    start = date(2026, 1, 1)
    user = make_user(seeded, start)
    assert ensure_missions(seeded, user, start + timedelta(days=90)) == []
    assert count(seeded, MissionInstance) == 0
    assert count(seeded, DailyPlan) == 0


def test_ensure_missions_records_the_daily_plan(seeded: Session) -> None:
    today = date(2026, 1, 1)
    user = make_user(seeded, today)
    ensure_missions(seeded, user, today)
    ensure_missions(seeded, user, today)
    assert count(seeded, DailyPlan) == 1


def _commit_winner(db: Session, user: User, day: date, templates: list[MissionTemplate]) -> set:
    """Simulate another request that planned and committed `day` first."""
    winner = [
        MissionInstance(user_id=user.id, mission_template_id=t.id, scheduled_date=day)
        for t in templates
    ]
    db.add(DailyPlan(user_id=user.id, plan_date=day))
    db.add_all(winner)
    db.commit()
    return {m.id for m in winner}


def _miss_first_plan_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the first existence check stale, as if the winner committed just after it."""
    real = planner.plan_exists
    stale = [True]
    monkeypatch.setattr(
        planner, "plan_exists", lambda *a: False if stale and stale.pop() else real(*a)
    )


def test_concurrent_request_reuses_the_winners_missions(
    seeded: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    today = date(2026, 1, 1)
    user = make_user(seeded, today)
    same_plan = [m.template for m in plan_daily_missions(seeded, user, 1, today)]
    winner_ids = _commit_winner(seeded, user, today, same_plan)
    _miss_first_plan_check(monkeypatch)

    result = ensure_missions(seeded, user, today)
    assert {m.id for m in result} == winner_ids
    assert count(seeded, MissionInstance) == len(winner_ids)
    assert count(seeded, DailyPlan) == 1


def test_concurrent_request_with_a_different_plan_does_not_double_the_day(
    seeded: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # E.g. the player changed track or language levels between the two requests: the plans differ,
    # so only the one-plan-per-day constraint can stop a second set of missions.
    today = date(2026, 1, 1)
    user = make_user(seeded, today)
    ours = {m.mission_template_id for m in plan_daily_missions(seeded, user, 1, today)}
    other = seeded.scalars(
        select(MissionTemplate).where(MissionTemplate.id.not_in(ours)).limit(2)
    ).all()
    winner_ids = _commit_winner(seeded, user, today, list(other))
    _miss_first_plan_check(monkeypatch)

    result = ensure_missions(seeded, user, today)
    assert {m.id for m in result} == winner_ids
    assert count(seeded, MissionInstance) == len(winner_ids)
    assert count(seeded, DailyPlan) == 1


def test_unexpected_integrity_error_is_not_swallowed(
    seeded: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    today = date(2026, 1, 1)
    user = make_user(seeded, today)
    # A mission pointing at a template that no longer exists (e.g. removed by a reseed).
    orphan = MissionInstance(
        user_id=user.id, mission_template_id=uuid.uuid4(), scheduled_date=today
    )
    monkeypatch.setattr(planner, "plan_daily_missions", lambda *a: [orphan])

    with pytest.raises(IntegrityError):
        ensure_missions(seeded, user, today)
    assert count(seeded, DailyPlan) == 0


def test_full_programme_rotates_evenly(seeded: Session) -> None:
    # Repeats are set by catalogue size; the planner's job is to spread them evenly.
    start = date(2026, 1, 1)
    user = make_user(seeded, start)
    uses: Counter[MissionTemplate] = Counter()
    for day in range(90):
        uses.update(m.template for m in ensure_missions(seeded, user, start + timedelta(day)))

    pools: dict[tuple, list[int]] = defaultdict(list)
    for template in seeded.scalars(
        select(MissionTemplate).where(MissionTemplate.day_offset.is_(None))
    ):
        assert uses[template] > 0, f"{template.name} never scheduled"
        pools[(template.phase, template.type)].append(uses[template])
    for pool, counts in pools.items():
        assert max(counts) - min(counts) <= 1, (pool, counts)


def test_next_day_rotates_templates(seeded: Session) -> None:
    start = date(2026, 1, 1)
    user = make_user(seeded, start)
    day1 = {m.mission_template_id for m in ensure_missions(seeded, user, start)}
    day2 = {m.mission_template_id for m in ensure_missions(seeded, user, start + timedelta(1))}
    assert day1 != day2


def test_completed_skills_feed_history(seeded: Session) -> None:
    start = date(2026, 1, 1)
    user = make_user(seeded, start)
    for m in ensure_missions(seeded, user, start):
        m.status = MissionStatus.COMPLETED
    seeded.commit()
    # Must not crash and must still produce a full day.
    assert len(ensure_missions(seeded, user, start + timedelta(days=1))) >= 3


# --- API ----------------------------------------------------------------------------------


def test_today_endpoint_plans_on_demand(
    client: TestClient, auth_headers: dict[str, str], seeded: Session
) -> None:
    resp = client.get("/api/missions", params={"date": "today"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert 3 <= len(body) <= 5
    assert {"language", "fitness", "study"} <= {m["template"]["type"] for m in body}

    again = client.get("/api/missions", params={"date": "today"}, headers=auth_headers).json()
    assert [m["id"] for m in again] == [m["id"] for m in body]


@pytest.mark.parametrize(
    ("days_since_start", "planned"),
    [pytest.param(89, True, id="day-90-plans"), pytest.param(90, False, id="day-91-empty")],
)
def test_today_endpoint_at_programme_end(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded: Session,
    days_since_start: int,
    planned: bool,
) -> None:
    """Day 90 is the last planned day; from day 91 on, "today" is an empty list, not an error."""
    user = seeded.scalar(select(User))
    user.program_start_date = datetime.now(ZoneInfo(user.time_zone)).date() - timedelta(
        days=days_since_start
    )
    seeded.commit()

    resp = client.get("/api/missions", params={"date": "today"}, headers=auth_headers)
    assert resp.status_code == 200
    if planned:
        assert resp.json()
    else:
        assert resp.json() == []  # an empty list: not null, not an error
    assert (count(seeded, MissionInstance) > 0) is planned


def test_time_zone_change_moves_today_without_duplicates(
    client: TestClient, auth_headers: dict[str, str], seeded: Session
) -> None:
    # UTC+14 and UTC-11 are 25 hours apart, so their local dates always differ.
    east, west = "Pacific/Kiritimati", "Pacific/Pago_Pago"
    user = seeded.scalar(select(User))
    user.program_start_date = datetime.now(ZoneInfo(west)).date() - timedelta(days=5)
    user.time_zone = west
    seeded.commit()

    def today_ids(zone: str) -> set[str]:
        client.patch("/api/user/me", json={"time_zone": zone}, headers=auth_headers)
        resp = client.get("/api/missions", params={"date": "today"}, headers=auth_headers)
        return {m["id"] for m in resp.json()}

    first = today_ids(west)
    second = today_ids(east)
    assert first and second and first.isdisjoint(second)
    assert today_ids(west) == first  # back west: the saved plan, nothing new
    assert count(seeded, MissionInstance) == len(first) + len(second)
    assert count(seeded, DailyPlan) == 2


def test_today_is_resolved_once_per_request(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A request that straddles local midnight plans the day it started on, not the next one."""
    user = seeded.scalar(select(User))
    zone = ZoneInfo(user.time_zone)
    today = date(2026, 1, 5)
    user.program_start_date = today - timedelta(days=4)
    seeded.commit()
    calls: list[datetime] = []

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            # The first reading is one microsecond before midnight; any later one is after it.
            moment = datetime.combine(today, datetime.max.time(), zone) + timedelta(
                microseconds=len(calls)
            )
            calls.append(moment)
            return moment.astimezone(tz)

    monkeypatch.setattr("app.routers.missions.datetime", Clock)
    resp = client.get("/api/missions", params={"date": "today"}, headers=auth_headers)

    assert resp.status_code == 200
    assert len(calls) == 1
    planned = seeded.scalars(select(MissionInstance.scheduled_date)).all()
    assert planned and set(planned) == {today}


def test_explicit_dates_do_not_plan(
    client: TestClient, auth_headers: dict[str, str], seeded: Session
) -> None:
    resp = client.get("/api/missions", params={"date": "2030-01-01"}, headers=auth_headers)
    assert resp.json() == []
    assert count(seeded, MissionInstance) == 0
