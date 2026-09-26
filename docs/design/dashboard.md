# Ops Console (Dashboard) — design

**Status:** approved design, not built. PRD increment #5. Language panels light up with #7b.
Check-ins are a later, separate increment ([checkins.md](checkins.md)).

Related: [language-focus.md](language-focus.md), [PRD](../PRD.md).

---

## Adjustments to the original brief

1. **Course progress can't be read from providers** (no public API; scraping is banned). It is
   the player ticking off modules, labelled `self-reported`.
2. **Expected pace comes from phase slot counts, not planned rows.** Missions are planned only
   when the player opens the app, so planned rows would never count a skipped day.
3. **One focus mission a day, rotating languages**, not one per language.
4. **Scenario stages** need a stage engine that doesn't exist yet; until then the widget shows
   scenario missions completed.

---

## Visual style

- Extend the existing tokens in `frontend/src/index.css`; don't replace them. Add `--cyan`,
  `--amber`, `--red`, `--mono` (JetBrains Mono / IBM Plex Mono / `ui-monospace`) and `--rtl`
  (Noto Naskh Arabic, Vazirmatn, Noto Sans Hebrew).
- Arabic, Farsi and Hebrew text always uses the `--rtl` stack with `dir="auto"` or explicit
  `lang`/`dir`. The terminal look is for chrome and numbers only.
- Panels: 1px border, box-drawing title in the `<h2>`, no rounded corners, 2px left border in
  the status colour.
- Scanlines and grid are CSS gradients on the console container. They are disabled under
  `prefers-reduced-motion` and `prefers-contrast: more`. Nothing animates except the clock.
- Contrast is WCAG AA or better. **Colour is never the only signal:** every status has a text
  label.

```
┌ MIDRASHA // OPS CONSOLE ──────────────── DAY 034/090 · 56 DAYS REMAINING · T-07:42:19 ┐
├─ STATUS // CHECK-INS (only when check-ins are enabled) ──────────────────────────────┤
├─ PRIORITY ACTIONS (NEXT 24H) ────────────────────────────────────────────────────────┤
│ 1. [FA] BEHIND  Complete a 10-min focus session on Farsi mistake words.              │
│ 2. [OSINT] BEHIND  Complete today's OSINT mission: "Verify a breaking story".        │
│ 3. MAINTAIN  Clear 64 reviews due across all languages.                               │
├─ OVERALL ─────────────────────────────┬─ SCHEDULE STATUS ─────────────────────────────┤
│ ACTUAL         [███░░░░░░░] 27%       │ ARABIC   ON TRACK  Δ +2% vs expected pace      │
│ EXPECTED PACE  [████░░░░░░] 35%       │ FARSI    BEHIND    Δ −12% vs expected pace     │
│ (missions completed ÷ programme total)│ HEBREW   AHEAD     Δ +7% vs expected pace      │
│ LANG 36 · FIT 40 · STUDY 31 · OPS 29  │ Δ = relative difference, not percentage points │
├─ LEXICON ─────────────────────────────┼─ FOCUS LIST (MISTAKE-DRIVEN) ─────────────────┤
│ AR known 1,240 · introduced 1,690     │ AR  87 words   [ START FOCUS SESSION ]         │
│    expected pace 1,560 · target 5,000 │ FA  64 words   [ START FOCUS SESSION ]         │
├─ ACTIVE COURSES ─────────────────────────────────────────────────────────────────────┤
│ ▶ NetAcad Intro to Cybersecurity  [████░░░░░░] 42%  (self-reported · 5/12 modules)   │
└───────────────────────────────────────────────── SIMULATION · FICTIONAL SCENARIOS ONLY ┘
```

Stack: React + CSS only. Bars are Unicode text with ARIA `role="progressbar"` and
`aria-valuenow`; the block characters are `aria-hidden`. No chart library (uPlot, MIT, only if a
sparkline is ever needed).

---

## Core widgets

All widgets read one `GET /api/dashboard` response. Nothing is computed from raw rows in the
browser.

| Widget | Shows |
|---|---|
| Countdown | `DAY 034/090 · 56 DAYS REMAINING · T-HH:MM:SS` to `day_ends_at` (UTC, computed server-side in the player's time zone, DST-safe). `STANDBY` before day 1; `PROGRAMME COMPLETE · FINAL DEBRIEF` after day 90. |
| Overall | **ACTUAL** (missions completed ÷ programme total) and **EXPECTED PACE** (what perfect attendance would give by today) as two separately labelled bars, plus the per-pillar breakdown. |
| Schedule status | Per track: label, `ON TRACK` / `AHEAD` / `BEHIND` / `CALIBRATING`, and `Δ ±N% vs expected pace`. A footnote says Δ is relative. |
| Lexicon | Per language: words **known** (headline), introduced, mature, expected pace to date, and the 5,000 **target** (reachable only with surge packs). |
| Focus list | Mistake words per language, with **Start focus session**; `FOCUS LIST CLEAR` at 0. |
| Active courses | Module-based %, `self-reported`, BEHIND when below expected by more than the threshold. |
| Priority actions | Up to 3 numbered, most urgent first; every one links inside the app or to a course URL. |
| Check-in status | Only when check-ins are enabled; see [checkins.md](checkins.md#dashboard-integration). |

Files: replace `pages/Dashboard.tsx` (today's cards move below as `TODAY'S ORDERS`);
`components/console/*`; `hooks/useDashboard.ts`, `hooks/useCountdown.ts`; `Dashboard` types in
`api/types.ts`.

Refresh without a live connection: on mount, on window focus, after any completion, review or
check-in mutation, and when the countdown hits zero. No WebSockets, no polling timer.

---

## Data & logic requirements

`GET /api/dashboard` requires login; every query filters by `current_user.id`. It returns
`DashboardOut`. Logic lives in `app/services/dashboard.py` as pure functions over pre-loaded
counts (the `select_templates` pattern).

Key fields: `local_date`, `program_day`, `days_remaining`, `phase`, `day_ends_at`, `state`;
`overall {completed, total, expected_to_date, actual_pct, expected_pct, by_pillar}`;
`lexicon[] {language, known, introduced, mature, target, expected_to_date, focus_count,
reviews_due}`; `courses[]`; `tracks[] {track, label, actual, expected, delta_pct, status}`;
`actions[]`; and, when enabled, `checkins` (the `GET /api/checkin-status` payload).

**Actual vs expected are always separate fields and separate labels.** The API never returns a
single blended "progress" number.

**Expected-pace curves** (linear within each phase):

| Track | Actual | Expected by programme day `d` |
|---|---|---|
| Overall / per pillar | completed missions | sum of the phase slot counts for days 1…d, limited to the pillar's slot types (`expected_missions_through(day, types)` exported by the planner) |
| Language ℓ | words introduced | piecewise linear: 420 by day 21, 1,720 by day 60, ≈ 2,820 by day 90 |
| Retention (flag only) | known ÷ introduced | `RETENTION LOW` below 0.5 once more than 200 words are introduced |
| Course | modules done ÷ total | linear from `start_day` to `target_day` (catalogue fields) |
| OSINT, scenarios | completed missions of that type | slot-based |
| Fitness | completed fitness missions | slot-based; breakdown only, never a BEHIND alarm |

Missed check-in windows **do not** change these curves. Compliance is reported separately (see
[checkins.md](checkins.md#completion-logging--metrics)).

**Status thresholds.**

```python
GRACE_UNITS = {"words": 60, "missions": 3, "modules": 1}   # below this: CALIBRATING

def track_status(actual: float, expected: float, unit: str) -> tuple[str, float | None]:
    if expected < GRACE_UNITS[unit]:
        return "calibrating", None
    delta = (actual - expected) / expected * 100   # relative difference, not percentage points
    if delta > 5:
        return "ahead", delta
    if delta < -5:
        return "behind", delta   # UI: amber above -15, red at -15 or below
    return "on_track", delta
```

The UI always renders the delta as `Δ −12% vs expected pace` with the "relative" footnote, never
as a bare `−12%`.

**Priority actions** (deterministic, no LLM): collect candidates, sort by most negative delta,
keep three, fill the rest with maintenance actions. Candidates: today's focus mission when its
language is behind; a 10-minute focus session; a surge pack when more than 15 % behind and it's
not that language's rotation day; the next unticked course module; today's OSINT or scenario
mission; clearing reviews due; "slow intake" when retention is low; the final debrief after day
90. **A pending recovery task (check-ins) always takes place 1.** No action ever targets fitness
catch-up.

**Course modules.** Add `modules` (public syllabus headings: metadata, not content),
`start_day` and `target_day` to each catalogue resource. New table `resource_progress`
(`user_id`, `resource_id`, `module_index`, `completed_at`; unique on the three ids);
`PUT`/`DELETE /api/resources/{id}/modules/{i}`.

**Tests (pure functions first):** threshold boundaries; CALIBRATING below grace; skipped days
count against expected pace; language curve boundaries; action ranking and the limit of three;
no fitness action; day 0, day 91 and future start; another user's data never appears. Frontend:
`AsciiBar` exposes `aria-valuenow`; countdown ticks and rolls over (fake timers); BEHIND renders
the word; ACTUAL and EXPECTED PACE render as separate labelled bars; focus button hidden at 0.

---

## Completion Logging & Metrics (dashboard)

- Mistake tracking, focus-list membership and review ordering are defined in
  [language-focus.md](language-focus.md#completion-logging--metrics). **One FSRS scheduler**;
  mistakes are prioritised by queue order only.
- Dashboard aggregates come from one grouped query per request over `vocab_progress` (introduced,
  known, mature, focus, reviews due per language).
- `tracks[]` is snapshotted into the day's language-focus `MissionLog.metrics` as flat keys
  (`status_lang_fa`, `delta_lang_fa`) so the recruiter has a history without a new table.
- Check-in compliance metrics are listed in
  [checkins.md](checkins.md#completion-logging--metrics).

---

## Integration

- **Planner.** Read-only, plus one exported helper, `expected_missions_through(day, types)`, so
  the planner and dashboard share one definition of a full day.
- **Language focus.** Lexicon, focus list and language status read `vocab_progress`. Before
  #7b those panels render `MODULE OFFLINE · UNLOCKS WITH LANGUAGE FOCUS`.
- **Recruiter.** `tracks[]` statuses become structured facts, never raw text.

---

## Tone & Framing Notes (dashboard)

| Use | Avoid |
|---|---|
| status, track, on track / ahead / behind | grade, score out of 10, pass/fail |
| priority actions, orders, next 24h | homework, assignments, to-do |
| focus list, mistake words | "words you failed" |
| actual, expected pace, target | "progress" with no label |
| calibrating | no data yet |
| programme complete, final debrief | graduation |

- Short capitalised labels (`FARSI · BEHIND · Δ −12% vs expected pace`). Actions start with a
  verb and name one thing.
- **Schedule status is information, not punishment.** BEHIND never threatens streaks and never
  asks for more than one extra session. Consequences exist only in the opt-in check-in layer,
  which has its own rules ([checkins.md](checkins.md)).
- **Fitness never shows a BEHIND alarm and never suggests catch-up workouts.**
- `SIMULATION · FICTIONAL SCENARIOS ONLY` stays in the console footer, as well as the existing
  disclaimer.
- Self-reported numbers are labelled `self-reported`; 5,000 is labelled a target.

## Free / open-source tooling

React, Vite, react-router-dom, Vitest, Testing Library (MIT); JetBrains Mono / IBM Plex Mono,
Noto, Vazirmatn (SIL OFL 1.1, self-hosted); uPlot (MIT, optional). No analytics, telemetry,
third-party CDNs or paid dependencies. Every metric is computed on our backend from our own
tables.
