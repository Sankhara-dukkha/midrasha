"""Migrations against real PostgreSQL. SQLite can't run them (gen_random_uuid, ALTER constraints).

Set MIDRASHA_TEST_POSTGRES_URL to a server the tests may create databases on, e.g.
postgresql+psycopg://midrasha:midrasha@localhost:5432/midrasha. Each test gets its own throwaway
database, dropped afterwards. Without the variable these tests are skipped.
"""

import json
import os
import uuid
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models import MissionInstance, MissionTemplate, User
from app.services.catalog import load_catalog

POSTGRES_URL = os.environ.get("MIDRASHA_TEST_POSTGRES_URL")
BACKEND = Path(__file__).resolve().parents[1]
CATALOG = json.loads((BACKEND.parent / "db" / "seeds" / "catalog.json").read_text("utf-8"))

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL, reason="set MIDRASHA_TEST_POSTGRES_URL to run migration tests"
)


@pytest.fixture
def pg_engine() -> Iterator[Engine]:
    assert POSTGRES_URL
    name = f"midrasha_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(POSTGRES_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    engine = create_engine(make_url(POSTGRES_URL).set(database=name))
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def migrate(pg_engine: Engine) -> Callable[..., None]:
    """Run an alembic command (upgrade, downgrade, check) on the throwaway database."""

    def run(cmd: Callable[..., None], *args: str) -> None:
        cfg = Config(str(BACKEND / "alembic.ini"))
        cfg.attributes["configure_logger"] = False
        with pg_engine.begin() as conn:
            cfg.attributes["connection"] = conn
            cmd(cfg, *args)

    return run


def test_migrations_round_trip_and_match_models(
    pg_engine: Engine, migrate: Callable[..., None]
) -> None:
    migrate(command.upgrade, "head")
    migrate(command.check)  # raises if the models and migrations disagree
    migrate(command.downgrade, "base")
    assert set(inspect(pg_engine).get_table_names()) <= {"alembic_version"}
    migrate(command.upgrade, "head")
    assert "daily_plans" in inspect(pg_engine).get_table_names()


def test_daily_plans_backfill_records_each_planned_day_once(
    pg_engine: Engine, migrate: Callable[..., None]
) -> None:
    migrate(command.upgrade, "0002")

    d1, d2, d3 = date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)
    with Session(pg_engine) as db:
        load_catalog(db, CATALOG)
        templates = db.scalars(select(MissionTemplate).limit(3)).all()
        alice, bob = (
            User(email=f"{n}@example.com", password_hash="x", display_name=n, program_start_date=d1)
            for n in ("alice", "bob")
        )
        db.add_all([alice, bob])
        db.flush()
        planned = [
            (alice, d1, templates[0]),
            (alice, d1, templates[1]),  # two missions on one day -> still one plan
            (alice, d2, templates[2]),
            (bob, d1, templates[0]),
            # Nobody has missions on d3 (or any later day), so it must stay unplanned.
        ]
        db.add_all(
            MissionInstance(user_id=u.id, mission_template_id=t.id, scheduled_date=d)
            for u, d, t in planned
        )
        db.commit()
        alice_id, bob_id = alice.id, bob.id

    migrate(command.upgrade, "0003")

    with pg_engine.connect() as conn:
        rows = conn.execute(text("SELECT user_id, plan_date FROM daily_plans")).all()
    assert sorted(rows) == sorted([(alice_id, d1), (alice_id, d2), (bob_id, d1)])
    assert all(plan_date < d3 for _, plan_date in rows)
