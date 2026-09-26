# MIDRASHA — Product Requirements

**Status:** v1 skeleton · **Last updated:** 2026-09-23

## 1. Purpose

MIDRASHA is a **fictional** 90-day intelligence-training simulation. The player is a "recruit"
contacted by a shadowy recruiter and trained across four pillars:

| Pillar | What the player builds |
|---|---|
| Cyber & OSINT | Security fundamentals, open-source research on synthetic data |
| Languages | Hebrew, Arabic, Farsi — vocabulary, script, code-switching |
| Physical fitness | Daily heart-rate / calorie / time targets |
| HUMINT & ethics | Relationship-intelligence judgement in fictional scenarios, scored for ethics |

The app schedules daily missions, links to external study resources, tracks completion and
performance, and gives in-character feedback (text + TTS audio). It is a serious game for
self-directed learning. **It is not operational training and gives no real-world operational
advice.**

## 2. Users

All players — including the author — start at **zero knowledge** in every pillar. Prior
certifications are extra context only, never a prerequisite.

| Persona | Description | Needs |
|---|---|---|
| **Self-directed learner** (primary) | Adult wanting a structured, motivating path into cyber/OSINT and languages | Clear daily plan, links to free/cheap courses, honest progress tracking |
| **Career switcher** | Moving towards security, research or journalism | Track-specific missions (`cyber`, `osint`, `journalist`, `general`) |
| **Language enthusiast** | Mainly wants tri-language practice with narrative motivation | Language emphasis setting, drills, audio |

## 3. Core loop (blended learning)

1. **Pre-training (outside the app).** The app recommends specific external resources
   (e.g. free/audit Coursera cyber intro, Cisco NetAcad *Introduction to Cybersecurity*, a
   beginner OSINT course). The player studies on those platforms.
2. **Knowledge checks (in the app).** Short quizzes and exercises on cyber, OSINT and ethics
   (e.g. spot the phishing email). These verify learning instead of trusting self-report.
3. **Field application (missions).** Missions need that knowledge:
   - Cyber: CTF-style tasks against **synthetic lab services** only.
   - OSINT: map **fictional** social networks, geolocate **synthetic** images, verify
     **synthetic** news.
   - Languages: follow tri-language recruiter instructions.
   - Fitness: hit numeric HR / calorie / time targets.

## 4. Programme structure

| Phase | Days | Focus |
|---|---|---|
| Induction | 1–21 | Foundations: basic study, alphabets, simple fitness |
| Specialisation | 22–60 | Harder missions matched to skill tags and player progress |
| Operations | 61–90 | Integrated scenarios mixing several skills |

Each day: 3–5 missions — normally 1 language, 1 fitness, 1 study, and 1 OSINT/scenario when
available (Operations: 1 scenario + 1 OSINT). Planning is data-driven (phase rules, templates and
skill tags in `app/services/planner.py` and `db/seeds/catalog.json`), not hard-coded. Missions are
planned the first time the player asks for "today"; `program_day` counts from the player's
`program_start_date` (their local registration date), and "today" is the date in the player's
`time_zone` setting. "Today" is resolved once per request, so a request that straddles local
midnight plans the day it started on; any other `date` value must be `YYYY-MM-DD`, or the API
returns 422. Changing time zone can shift "today" by a day; the player gets that day's
plan, never a duplicate. A `daily_plans` row (unique per user and date) is written in the same
transaction as the day's missions, so each day is planned exactly once, even under concurrent
requests. Settings changes (track, language levels) affect days not yet planned; an
already-planned day is never re-planned. After day 90 no new missions are planned and "today"
returns an empty list. With the seed catalogue that is 4 missions a day on days 1–60 and 5 on
days 61–90.

Day-pinned templates (`day_offset`) always win their slot. The catalogue loader rejects a
catalogue where a pinned template could not be scheduled (two pinned for one slot, or a type
with no slot in that phase), and writes nothing.

Known limitations:
- A day the player never opens is never planned, so it has no missions and does not count as
  missed.
- The programme length is fixed at 90 days.
- The Operations catalogue is thin (one OSINT, one study and three scenario templates for 30
  days), so Operations missions repeat often. The planner spreads repeats evenly, but variety
  needs more content.
- An existing database needs migration `0003` (which backfills `daily_plans` from existing
  missions) before this planner runs. The backfill uses PostgreSQL's `gen_random_uuid()`, so
  migrations are tested against PostgreSQL, not SQLite.

## 5. Main workflows

1. **View today's missions** — dashboard lists today's missions (player's local date) as cards.
2. **Complete external study tasks** — open a mission, follow links to the resource, mark it
   complete.
3. **Log fitness and language drills** — record start/end time, notes and metrics
   (HR, kcal, vocab correct, …).
4. **Receive recruiter feedback** — daily briefing, nudges ("behind schedule"), daily debrief;
   text plus a "Play audio" TTS button.
5. **Take in-game tests and missions** — quizzes, OSINT/cyber exercises, scenario missions.
6. **Adjust settings** — time zone, language emphasis, fitness baseline.

## 6. Data model (v1)

- **User** — email, password hash, display name, time zone, language levels 0–5 (he/ar/fa),
  fitness baseline (target HR zone, daily kcal goal), track.
- **StudyResource** — type (video/course/book/article), provider (Coursera/Udemy/NetAcad/Other),
  title, URL, estimated hours, skill tags.
- **MissionTemplate** — name, description, type (language/fitness/study/osint/scenario), skill
  tags, `day_offset` (1–90) and/or `phase`, difficulty 1–5, required resources.
- **MissionInstance** — a template assigned to a user on a date; status
  assigned/in_progress/completed/failed.
- **MissionLog** — one session on a mission: times, notes, recruiter score 0–100, metrics (JSON).

## 7. Features and increments

| # | Increment | Status |
|---|---|---|
| 1 | Skeleton: repo layout, FastAPI, React routing, Postgres migration | **Done** |
| 2 | Auth (register/login, JWT) | **Done (basic)** |
| 3 | Data models + migration | **Done** |
| 4 | Mission planner `plan_daily_missions(user, program_day)` + on-login scheduling | **Done** |
| 5 | Dashboard + mission detail with resources and completion logging | Partly (read-only) |
| 6 | TTS stub `POST /api/tts` (he/ar/fa) + "Play audio" | Planned |
| 7 | Language drill (flashcards, code-switching sentences, progress) | Planned |
| 8 | Recruiter rules engine (briefing, nudges, debrief, unlocks) | Planned |
| 9 | Knowledge checks (quizzes, phishing ID) | Planned |
| 10 | Deployment (Dockerfiles; Vercel/Netlify + Render/Fly.io) | Planned |
| 11 | LLM-generated recruiter messages (Claude API) | Later |
| 12 | Opt-in check-ins, recovery tasks, discipline voice | Designed |

Designs for increments not yet built: [dashboard](design/dashboard.md) (#5),
[language focus](design/language-focus.md) (#7), [check-ins](design/checkins.md) (#12).

## 8. Constraints

### Ethics and safety (non-negotiable)

- **Fictional, closed world.** All targets, extremist groups, organisations and relationships are
  invented. No real people are targeted, profiled or contacted.
- **No real-world operations.** No instructions to interact with real extremists, terrorist
  recruiters or vulnerable individuals. No hunting real extremist content.
- **No grooming, trafficking or abuse training** of any kind, including "honeypot" techniques
  aimed at real people. Honeypot/OSINT concepts appear only in fictional scenarios or curated,
  clearly lawful case material.
- **Ethics is scored.** HUMINT/relationship missions penalise manipulative, coercive or
  harmful choices and reward consent, honesty, proportionality and duty of care. Scenarios
  address psychological impact on both the player and fictional characters.
- **Always labelled as a simulation.** The UI shows a persistent "fictional simulation, not
  operational advice" notice.
- **Lawful cyber practice only.** Cyber exercises target synthetic, app-provided lab services,
  never third-party systems.

### Content conventions

- Invented setting, reused across missions: the port city of **Port Venn** and the invented
  group the **Orchard Circle**. New places, groups and people must be invented too.
- HUMINT scenario descriptions state the scoring: honesty, consent, proportionality and duty of
  care score; pressure, deception and manipulation lose points.
- OSINT and cyber missions reference synthetic, in-app material only.

### Product

- Zero-knowledge baseline; every mission is achievable with the linked resources plus in-app
  explanations.
- Works on desktop and mobile web. Correct right-to-left rendering for Hebrew, Arabic and Farsi.
- External resources are linked, never scraped or re-hosted.

### Technical

- React + Vite (TypeScript), FastAPI (Python 3.12), PostgreSQL, Alembic.
- Email/password auth for v1.
- Secrets only in environment variables.

## 9. Out of scope for v1

Social/multiplayer features, payments, native mobile apps, wearable integrations (metrics are
entered manually), real LLM calls (templated text first).
