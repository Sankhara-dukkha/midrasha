import uuid
from datetime import date, timedelta

import pytest

from app.models import MissionTemplate, User
from app.models.enums import MissionType, Phase, Track
from app.services.planner import (
    PlayerHistory,
    phase_for_day,
    select_templates,
)

L, F, S, OS, X = (
    MissionType.LANGUAGE,
    MissionType.FITNESS,
    MissionType.STUDY,
    MissionType.OSINT,
    MissionType.SCENARIO,
)
TODAY = date(2026, 3, 1)


def tpl(
    name: str,
    type: MissionType,
    *,
    phase: Phase | None = Phase.INDUCTION,
    day: int | None = None,
    difficulty: int = 1,
    tags: list[str] | None = None,
) -> MissionTemplate:
    return MissionTemplate(
        id=uuid.uuid4(),
        name=name,
        description=name,
        type=type,
        phase=phase,
        day_offset=day,
        difficulty=difficulty,
        skill_tags=tags or [],
    )


def recruit(**overrides) -> User:
    fields = dict(
        email="r@example.com",
        password_hash="x",
        display_name="R",
        track=Track.GENERAL,
        language_level_hebrew=0,
        language_level_arabic=0,
        language_level_farsi=0,
    )
    return User(**(fields | overrides))


def names(chosen: list[MissionTemplate]) -> list[str]:
    return [t.name for t in chosen]


def pick(templates, day=5, user=None, history=None) -> list[MissionTemplate]:
    return select_templates(
        user or recruit(), day, templates, history or PlayerHistory(), on_date=TODAY
    )


BASIC = [
    tpl("lang", L),
    tpl("fit", F),
    tpl("study", S),
    tpl("osint", OS),
]


# --- phases ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("day", "phase"),
    [
        (1, Phase.INDUCTION),
        (21, Phase.INDUCTION),
        (22, Phase.SPECIALISATION),
        (60, Phase.SPECIALISATION),
        (61, Phase.OPERATIONS),
        (90, Phase.OPERATIONS),
    ],
)
def test_phase_boundaries(day: int, phase: Phase) -> None:
    assert phase_for_day(day).phase == phase


@pytest.mark.parametrize("day", [0, 91])
def test_phase_rejects_days_outside_programme(day: int) -> None:
    with pytest.raises(ValueError):
        phase_for_day(day)


# --- slot filling ---------------------------------------------------------------------------


def test_one_mission_per_slot() -> None:
    chosen = pick(BASIC)
    assert [t.type for t in chosen] == [L, F, S, OS]


def test_osint_slot_is_optional() -> None:
    chosen = pick([t for t in BASIC if t.type != OS])
    assert [t.type for t in chosen] == [L, F, S]


def test_scenario_fills_osint_slot_when_no_osint() -> None:
    chosen = pick([*BASIC[:3], tpl("scn", X)])
    assert names(chosen) == ["lang", "fit", "study", "scn"]


def test_fresh_scenario_beats_repeated_osint() -> None:
    used = tpl("osint", OS)
    history = PlayerHistory(last_assigned={used.id: TODAY - timedelta(days=1)})
    assert names(pick([*BASIC[:3], used, tpl("scn", X)], history=history))[3] == "scn"


def test_never_repeats_a_template_within_a_day() -> None:
    chosen = pick([*BASIC, tpl("osint2", OS)])
    assert len({t.id for t in chosen}) == len(chosen)


def test_operations_day_has_scenario_and_osint() -> None:
    ops = [
        tpl("lang", L, phase=Phase.OPERATIONS, difficulty=3),
        tpl("fit", F, phase=Phase.OPERATIONS, difficulty=3),
        tpl("study", S, phase=Phase.OPERATIONS, difficulty=3),
        tpl("scn", X, phase=Phase.OPERATIONS, difficulty=4),
        tpl("osint", OS, phase=Phase.OPERATIONS, difficulty=3),
    ]
    chosen = pick(ops, day=75)
    assert len(chosen) == 5
    assert chosen[3].type == X


# --- eligibility ----------------------------------------------------------------------------


def test_other_phases_are_excluded() -> None:
    late = tpl("late-lang", L, phase=Phase.OPERATIONS, difficulty=3)
    chosen = pick([late, *BASIC[1:]])
    assert "late-lang" not in names(chosen)


def test_difficulty_outside_phase_range_is_excluded() -> None:
    too_hard = tpl("hard-lang", L, difficulty=5)
    assert "hard-lang" not in names(pick([too_hard, *BASIC[1:]]))


def test_day_pinned_template_wins_on_its_day_only() -> None:
    pinned = tpl("day1-lang", L, phase=None, day=1)
    templates = [*BASIC, pinned]
    assert names(pick(templates, day=1))[0] == "day1-lang"
    assert names(pick(templates, day=2))[0] == "lang"


# --- ranking --------------------------------------------------------------------------------


def test_fresh_templates_beat_repeats() -> None:
    old, new = tpl("old", S), tpl("new", S)
    history = PlayerHistory(last_assigned={old.id: TODAY - timedelta(days=1)})
    assert "new" in names(pick([old, new], history=history))


def test_least_recent_repeat_is_chosen_when_all_used() -> None:
    a, b = tpl("a", F), tpl("b", F)
    history = PlayerHistory(
        last_assigned={a.id: TODAY - timedelta(days=1), b.id: TODAY - timedelta(days=5)}
    )
    assert names(pick([a, b], history=history)) == ["b"]


def test_track_affinity() -> None:
    cyber = tpl("cyber-study", S, tags=["cyber_basics"])
    osint = tpl("osint-study", S, tags=["osint_basics"])
    assert names(pick([osint, cyber], user=recruit(track=Track.CYBER))) == ["cyber-study"]
    assert names(pick([cyber, osint], user=recruit(track=Track.OSINT))) == ["osint-study"]


def test_builds_on_completed_skills_in_specialisation() -> None:
    related = tpl("geo", OS, phase=Phase.SPECIALISATION, difficulty=3, tags=["osint_image"])
    unrelated = tpl("other", OS, phase=Phase.SPECIALISATION, difficulty=3, tags=["misc_x"])
    history = PlayerHistory(completed_tags={"osint_image"})
    assert names(pick([unrelated, related], day=30, history=history)) == ["geo"]


def test_difficulty_ramps_through_phase() -> None:
    easy = tpl("easy", F, phase=Phase.SPECIALISATION, difficulty=2)
    hard = tpl("hard", F, phase=Phase.SPECIALISATION, difficulty=4)
    assert names(pick([easy, hard], day=22)) == ["easy"]
    assert names(pick([easy, hard], day=60)) == ["hard"]


def test_language_level_raises_language_difficulty() -> None:
    easy = tpl("easy", L, phase=Phase.SPECIALISATION, difficulty=2)
    hard = tpl("hard", L, phase=Phase.SPECIALISATION, difficulty=4)
    beginner = recruit()
    advanced = recruit(language_level_hebrew=3, language_level_arabic=3, language_level_farsi=3)
    assert names(pick([easy, hard], day=22, user=beginner)) == ["easy"]
    assert names(pick([easy, hard], day=22, user=advanced)) == ["hard"]


def test_operations_prefers_integrated_scenarios() -> None:
    single = tpl("single", X, phase=Phase.OPERATIONS, difficulty=4, tags=["osint_geolocation"])
    mixed = tpl(
        "mixed",
        X,
        phase=Phase.OPERATIONS,
        difficulty=4,
        tags=["osint_geolocation", "cyber_networking", "humint_ethics"],
    )
    assert names(pick([single, mixed], day=75))[0] == "mixed"


def test_selection_is_deterministic() -> None:
    templates = [tpl(f"s{i}", S) for i in range(5)]
    assert names(pick(templates)) == names(pick(list(reversed(templates))))
