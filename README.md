# MIDRASHA

A fictional 90-day intelligence-training serious game: cyber/OSINT, Hebrew/Arabic/Farsi,
fitness, and HUMINT ethics. **Simulation only. Not operational advice.**

- Product: [docs/PRD.md](docs/PRD.md)
- Engineering rules: [CLAUDE.md](CLAUDE.md)

## Quick start (Windows, Git Bash)

Prerequisites: Python 3.12, Node 22+, Docker Desktop (for Postgres).

```bash
# 1. Database
docker compose up -d db

# 2. Backend
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
cp .env.example .env          # then set JWT_SECRET to a long random value
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m app.seed               # load resources + mission templates
.venv/Scripts/fastapi dev app/main.py        # http://localhost:8000/docs

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev                                   # http://localhost:5173
```

Smoke test (API running, database migrated and seeded):

```bash
curl -s localhost:8000/api/auth/register -H 'Content-Type: application/json'   -d '{"email":"me@example.com","password":"correct-horse-battery","display_name":"Me"}'
TOKEN=$(curl -s localhost:8000/api/auth/login -H 'Content-Type: application/json'   -d '{"email":"me@example.com","password":"correct-horse-battery"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s "localhost:8000/api/missions?date=today" -H "Authorization: Bearer $TOKEN"   # plans day 1
```

## Content and ethics

Every person, group and place in MIDRASHA is invented, and OSINT/cyber work uses synthetic data
only. HUMINT scenarios score ethical conduct and penalise manipulation. See
[PRD §8](docs/PRD.md#8-constraints) before adding missions.

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest
cd frontend && npm test
```

## Pre-merge checklist

**Do not merge until this checklist is green.** The unit tests run on SQLite; migrations (and
the `daily_plans` backfill) only run on PostgreSQL, so any change to models, migrations, the
planner or the catalogue must also pass this. Needs Docker Desktop running (on Windows that
requires WSL 2) or another local PostgreSQL 17 (then adjust host/port in the URLs and use its own
`createdb`/`psql`/`dropdb`). Needs `backend/.env` with `JWT_SECRET` set (see Quick start): alembic
and the seed load the app settings too.

```bash
docker compose up -d db && docker compose ps          # db must show "healthy"
docker compose exec db createdb -U midrasha midrasha_premerge
cd backend

# 1. Lint and tests, including the PostgreSQL migration tests (skipped without the variable)
.venv/Scripts/ruff check . ../db/migrations && .venv/Scripts/ruff format --check . ../db/migrations
MIDRASHA_TEST_POSTGRES_URL=postgresql+psycopg://midrasha:midrasha@localhost:5432/midrasha \
  .venv/Scripts/python -m pytest -rs                 # expect no skips

# 2. Migrations on the throwaway database: up, models match, down, up again
export DATABASE_URL=postgresql+psycopg://midrasha:midrasha@localhost:5432/midrasha_premerge
.venv/Scripts/alembic upgrade head
.venv/Scripts/alembic check                          # "No new upgrade operations detected."
.venv/Scripts/alembic downgrade base
.venv/Scripts/alembic upgrade head

# 3. Seed twice: both runs print the same counts
.venv/Scripts/python -m app.seed
.venv/Scripts/python -m app.seed
docker compose exec db psql -U midrasha -d midrasha_premerge -c \
  "SELECT (SELECT count(*) FROM mission_templates) t, (SELECT count(*) FROM study_resources) r;"

# 4. API smoke test: in another terminal, export the same DATABASE_URL and run
#    `.venv/Scripts/fastapi dev app/main.py`; then
curl -s localhost:8000/api/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"premerge@example.com","password":"correct-horse-battery","display_name":"PM"}'
TOKEN=$(curl -s localhost:8000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"premerge@example.com","password":"correct-horse-battery"}' \
  | .venv/Scripts/python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
ids() { curl -s "localhost:8000/api/missions?date=today" -H "Authorization: Bearer $TOKEN" \
  | .venv/Scripts/python -c "import sys,json;print(sorted(m['id'] for m in json.load(sys.stdin)))"; }
ids; ids                                             # same non-empty list twice
docker compose exec db psql -U midrasha -d midrasha_premerge -c \
  "SELECT user_id, plan_date, count(*) FROM daily_plans GROUP BY user_id, plan_date;"  # one row

# 5. Clean up (stop the API first)
unset DATABASE_URL
docker compose exec db dropdb -U midrasha midrasha_premerge
```

If a step fails, fix it and run the whole list again.

## Layout

```
backend/     FastAPI app (routers, models, schemas, services) + tests
frontend/    React + Vite app (pages, components, hooks, api)
db/          Alembic migrations, seed scripts
prompts/     recruiter persona + language drill prompts
docs/        PRD, design/ (designs for increments not yet built)
```
