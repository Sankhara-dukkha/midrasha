# MIDRASHA — guidance for Claude Code

Read [docs/PRD.md](docs/PRD.md) at the start of every session. It defines the product and its
ethics constraints; this file defines how we build it.

## Stack

| Layer | Choice |
|---|---|
| Frontend | React 19 + Vite + TypeScript (strict), react-router-dom |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2.0 (typed `Mapped[...]`), Python 3.12 |
| Database | PostgreSQL 17; migrations with Alembic in `db/migrations/` |
| Auth | Email + password (bcrypt), JWT bearer tokens (PyJWT) |
| Tests | pytest (backend), Vitest + Testing Library (frontend) |
| Lint/format | ruff (backend), oxlint (frontend) |

## Layout

```
backend/app/        main.py, core/ (config, security), db.py, deps.py,
                    models/, schemas/, routers/, services/ (business logic goes here)
backend/tests/      pytest; SQLite in-memory via conftest.py
db/migrations/      Alembic (config at backend/alembic.ini)
db/seeds/           catalog.json (study resources + mission templates), loaded by app.seed
frontend/src/       api/, components/, hooks/, pages/
prompts/            recruiter persona and language-drill prompt templates
docs/               PRD.md
```

## Commands

Run from the repo root unless noted.

```bash
docker compose up -d db                                   # local Postgres
cd backend && .venv/Scripts/alembic upgrade head          # apply migrations (needs .env)
cd backend && .venv/Scripts/python -m app.seed            # load db/seeds/catalog.json (idempotent)
cd backend && .venv/Scripts/fastapi dev app/main.py       # API on :8000
cd backend && .venv/Scripts/python -m pytest              # backend tests
cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .
cd frontend && npm run dev                                # UI on :5173 (proxies /api)
cd frontend && npm test && npm run lint && npm run typecheck
```

## Working agreement

- **Plan first.** Before a feature, outline backend (models/routes/services), frontend
  (components/hooks/pages) and tests. Then code.
- **Test first** for major features (mission planner, TTS endpoint, language drill).
- **Small, reviewable diffs**, one increment at a time (see PRD §7). Stop after each for review.
- Do not start the next increment unless asked.

## Coding standards

### Backend
- Every request/response body is a Pydantic model. Never return ORM objects without a
  `response_model`; never expose `password_hash`.
- Validate at the edge: ranges (`Field(ge=, le=)`), enums, IANA time zones, max lengths.
- Mirror important invariants as DB `CheckConstraint`s too.
- Business logic lives in `app/services/`, not in routers.
- Schema changes need an Alembic migration. Autogenerate against Postgres, then **read and edit**
  the result. Keep the naming convention in `models/base.py`; names must stay ≤ 63 chars.
- Enums are `StrEnum` stored as VARCHAR + CHECK (`str_enum()`), not native PG enums.
- Types: full annotations; `ruff check` and `ruff format` must pass.

### Frontend
- TypeScript strict; no `any`. API types live in `src/api/types.ts` and mirror backend schemas.
- All HTTP goes through `src/api/client.ts` (`apiFetch`). No direct `fetch` in components.
- Any element showing Hebrew/Arabic/Farsi or user text gets `dir="auto"` (or explicit
  `dir="rtl"` + `lang`).
- Never use `dangerouslySetInnerHTML`.
- Tests with Vitest + Testing Library; query by role/text, not class names.

## Security rules

- **No secrets in the repo.** Config comes from environment variables (`.env` is gitignored;
  keep `.env.example` updated with placeholders only). `JWT_SECRET` must be ≥ 32 chars.
- Frontend env vars (`VITE_*`) are public — never put keys there. Third-party API keys (TTS,
  LLM) are used **only** by the backend.
- Passwords: bcrypt, 10–72 bytes. Login errors don't reveal whether an email exists.
- Authorisation: every user-owned resource is filtered by `current_user.id`. Return 404, not
  403, for other users' resources.
- Validate all input server-side even if the UI validates too.
- CORS is an explicit allow-list (`CORS_ORIGINS`).
- JWT is kept in `sessionStorage` for v1 (XSS-exposed, so no untrusted HTML rendering). Revisit
  httpOnly cookies + CSRF before public launch. Login rate limiting is also still TODO.

## Do not do

- Do not scrape, fetch, store or link live extremist, terrorist or hate content.
- Do not write content, prompts or missions that teach grooming, manipulation of real people,
  trafficking, abuse, stalking or doxxing.
- Do not create missions that tell the player to contact, profile or investigate real people or
  real organisations. All targets are fictional; OSINT runs on synthetic data.
- Do not create cyber exercises aimed at real third-party systems. Use app-provided synthetic
  labs only.
- Do not remove the simulation disclaimer or the ethics scoring from HUMINT missions.
- Do not scrape or re-host course content from Coursera, Udemy, NetAcad, etc.; link to it.
- Do not commit `.env`, credentials, tokens, or real personal data.
