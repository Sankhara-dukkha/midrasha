"""Daily mission planner.

Rules are data (PHASES, TRACK_TAG_PREFIXES); `select_templates` is a pure function over them so
it can be tested without a database. `ensure_missions` is the on-demand scheduler: the first
request for a player's "today" plans and stores that day's missions.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import DailyPlan, MissionInstance, MissionTemplate, User
from app.models.enums import MissionStatus, MissionType, Phase, Track

PROGRAM_DAYS = 90

LANG, FIT, STUDY, OSINT, SCEN = (
    MissionType.LANGUAGE,
    MissionType.FITNESS,
    MissionType.STUDY,
    MissionType.OSINT,
    MissionType.SCENARIO,
)


@dataclass(frozen=True)
class Slot:
    """One mission per slot per day. `types` is in order of preference; freshness outranks it.

    A slot with no eligible template is skipped, so a day has 3 core missions plus any extras.
    """

    types: tuple[MissionType, ...]


@dataclass(frozen=True)
class PhaseRule:
    phase: Phase
    first_day: int
    last_day: int
    min_difficulty: int
    max_difficulty: int
    slots: tuple[Slot, ...]
    # Operations rewards scenarios that combine several pillars (cyber_, osint_, lang_, ...).
    reward_integration: bool = False


_CORE = (Slot((LANG,)), Slot((FIT,)), Slot((STUDY,)))

# Difficulty bands overlap on purpose (2 and 3 each span two phases) so the step between phases
# is gradual rather than a jump.
PHASES: tuple[PhaseRule, ...] = (
    PhaseRule(Phase.INDUCTION, 1, 21, 1, 2, (*_CORE, Slot((OSINT, SCEN)))),
    PhaseRule(Phase.SPECIALISATION, 22, 60, 2, 4, (*_CORE, Slot((OSINT, SCEN)))),
    PhaseRule(
        Phase.OPERATIONS,
        61,
        90,
        3,
        5,
        (*_CORE, Slot((SCEN, OSINT)), Slot((OSINT, SCEN))),
        reward_integration=True,
    ),
)

TRACK_TAG_PREFIXES: dict[Track, tuple[str, ...]] = {
    Track.CYBER: ("cyber_",),
    Track.OSINT: ("osint_",),
    Track.JOURNALIST: ("osint_", "journalism_"),
    Track.GENERAL: (),
}

# Display order of a day's missions.
TYPE_ORDER: tuple[MissionType, ...] = (LANG, FIT, STUDY, SCEN, OSINT)


@dataclass
class PlayerHistory:
    """What the planner knows about a player's past, as of the day being planned."""

    last_assigned: dict[uuid.UUID, date] = field(default_factory=dict)
    completed_tags: set[str] = field(default_factory=set)


def phase_for_day(program_day: int) -> PhaseRule:
    for rule in PHASES:
        if rule.first_day <= program_day <= rule.last_day:
            return rule
    raise ValueError(f"program day must be 1-{PROGRAM_DAYS}, got {program_day}")


def program_day_for(user: User, on_date: date) -> int:
    return (on_date - user.program_start_date).days + 1


def _is_eligible(t: MissionTemplate, program_day: int, rule: PhaseRule) -> bool:
    if t.day_offset is not None:
        return t.day_offset == program_day
    return t.phase == rule.phase and rule.min_difficulty <= t.difficulty <= rule.max_difficulty


def _target_difficulty(user: User, t: MissionTemplate, program_day: int, rule: PhaseRule) -> float:
    if t.type == LANG:
        # Language difficulty follows the player's own levels, one step above their average.
        levels = (user.language_level_hebrew, user.language_level_arabic, user.language_level_farsi)
        target = sum(levels) / len(levels) + 1
    else:
        # Everything else ramps linearly through the phase.
        progress = (program_day - rule.first_day) / (rule.last_day - rule.first_day)
        target = rule.min_difficulty + progress * (rule.max_difficulty - rule.min_difficulty)
    return min(max(target, rule.min_difficulty), rule.max_difficulty)


def _affinity(user: User, t: MissionTemplate, history: PlayerHistory, rule: PhaseRule) -> int:
    tags = set(t.skill_tags or [])
    score = len(tags & history.completed_tags)
    prefixes = TRACK_TAG_PREFIXES.get(user.track, ())
    if prefixes and any(tag.startswith(prefixes) for tag in tags):
        score += 1
    if rule.reward_integration:
        pillars = {tag.split("_", 1)[0] for tag in tags}
        score += max(len(pillars) - 1, 0)
    return score


def select_templates(
    user: User,
    program_day: int,
    templates: Sequence[MissionTemplate],
    history: PlayerHistory,
    *,
    on_date: date,
) -> list[MissionTemplate]:
    """Pick one template per slot for `program_day`. Pure and deterministic.

    Ranking within a slot, most important first: pinned to this exact day; never assigned before
    (else least recently assigned); the slot's type preference; skill/track/integration affinity;
    difficulty nearest the target; name.
    """
    rule = phase_for_day(program_day)
    eligible = [t for t in templates if _is_eligible(t, program_day, rule)]

    def rank(t: MissionTemplate, slot: Slot) -> tuple:
        last = history.last_assigned.get(t.id)
        freshness = (0, 0) if last is None else (1, -(on_date - last).days)
        return (
            t.day_offset != program_day,
            freshness,
            slot.types.index(t.type),
            -_affinity(user, t, history, rule),
            abs(t.difficulty - _target_difficulty(user, t, program_day, rule)),
            t.name,
            str(t.id),
        )

    chosen: list[MissionTemplate] = []
    for slot in rule.slots:
        candidates = [t for t in eligible if t.type in slot.types and t not in chosen]
        if candidates:
            chosen.append(min(candidates, key=lambda t, slot=slot: rank(t, slot)))
    return chosen


def _load_history(db: Session, user: User, before: date) -> PlayerHistory:
    past = and_(MissionInstance.user_id == user.id, MissionInstance.scheduled_date < before)
    last_assigned = dict(
        db.execute(
            select(MissionInstance.mission_template_id, func.max(MissionInstance.scheduled_date))
            .where(past)
            .group_by(MissionInstance.mission_template_id)
        ).all()
    )
    completed = db.scalars(
        select(MissionTemplate.skill_tags)
        .join(MissionInstance, MissionInstance.mission_template_id == MissionTemplate.id)
        .where(past, MissionInstance.status == MissionStatus.COMPLETED)
    )
    return PlayerHistory(
        last_assigned=last_assigned,
        completed_tags={tag for tags in completed for tag in tags or []},
    )


def plan_daily_missions(
    db: Session, user: User, program_day: int, on_date: date
) -> list[MissionInstance]:
    """Build (but do not save) the missions for one programme day. Empty outside days 1-90.

    `on_date` is the calendar date being planned: it becomes `scheduled_date` and bounds the
    history (only earlier days count), so the result is the same whenever it is computed.
    """
    # Outside days 1-90 there is nothing to plan: return [] and write nothing. Callers treat []
    # as "no missions" (programme over or not started), never as an error.
    if not 1 <= program_day <= PROGRAM_DAYS:
        return []
    rule = phase_for_day(program_day)
    templates = db.scalars(
        select(MissionTemplate).where(
            or_(
                MissionTemplate.day_offset == program_day,
                and_(MissionTemplate.day_offset.is_(None), MissionTemplate.phase == rule.phase),
            )
        )
    ).all()
    history = _load_history(db, user, on_date)
    chosen = select_templates(user, program_day, templates, history, on_date=on_date)
    return [
        MissionInstance(
            user_id=user.id,
            mission_template_id=t.id,
            template=t,
            scheduled_date=on_date,
            status=MissionStatus.ASSIGNED,
        )
        for t in chosen
    ]


def missions_on(db: Session, user: User, on_date: date) -> list[MissionInstance]:
    stmt = (
        select(MissionInstance)
        .where(MissionInstance.user_id == user.id, MissionInstance.scheduled_date == on_date)
        .order_by(MissionInstance.created_at, MissionInstance.id)
    )
    missions = list(db.scalars(stmt).unique())
    return sorted(missions, key=lambda m: TYPE_ORDER.index(m.template.type))


def plan_exists(db: Session, user: User, on_date: date) -> bool:
    stmt = select(DailyPlan.id).where(DailyPlan.user_id == user.id, DailyPlan.plan_date == on_date)
    return db.scalar(stmt) is not None


def ensure_missions(db: Session, user: User, on_date: date) -> list[MissionInstance]:
    """Return the player's missions for `on_date`, planning and saving them if there are none.

    The DailyPlan row and the missions commit together, and only one request can insert the
    DailyPlan for a (user, date), so a day is planned exactly once even under concurrency.
    """
    if plan_exists(db, user, on_date):
        return missions_on(db, user, on_date)
    planned = plan_daily_missions(db, user, program_day_for(user, on_date), on_date)
    if not planned:
        return []
    db.add(DailyPlan(user_id=user.id, plan_date=on_date))
    db.add_all(planned)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Expected only when a concurrent request planned this day first; anything else is a bug.
        if not plan_exists(db, user, on_date):
            raise
    return missions_on(db, user, on_date)
