# Mandatory Check-Ins with Consequences (Hourly or 3-Block)

**Status:** approved in direction, not built. A separate increment after the dashboard (#5) and
before or alongside the recruiter rules engine (#8). Nothing here changes the planner's
selection logic.

Related: [dashboard.md](dashboard.md), [language-focus.md](language-focus.md), [PRD](../PRD.md).

An opt-in "operational discipline" layer. The player reports in on a fixed rhythm. Missing a
window has visible, recoverable consequences. Genuine emergencies are covered by a rate-limited
exemption. Everything is server-side state and timestamps: no cron jobs, external services or
analytics.

---

## Guardrails (apply to everything below)

1. **Opt-in.** Check-ins are `OFF` by default. The player turns on `3-BLOCK` or `HOURLY` in
   Settings, after a screen that explains the consequences and the drill voice.
2. **Active hours only.** No window is ever due outside the player's active hours (default
   08:00–22:00 local; at most 16 hours long). Nothing is enforced overnight.
3. **Stand down at any time.** Switching check-ins to `OFF` in Settings always works, takes
   effect immediately, is not rate-limited, and clears any lock. Past misses stay in the log.
   Consent is ongoing, not a one-time checkbox.
4. **Recoverable.** One recovery task restores normal operations, however many windows were
   missed. Recovery tasks don't stack (at most one outstanding).
5. **Never locked:** settings, the simulation disclaimer, check-in itself, exemptions, the
   recovery task, reviews due, fitness missions, account and data export/deletion.
6. **Fitness is never penalised.** No extra, doubled or catch-up workouts, ever.
7. **No runaway penalties.** After 24 hours with no check-in, the layer drops to `STAND-BY`: no
   more misses accrue. The next visit shows a short re-entry briefing and one recovery task
   (exact rules in [Pausing after 24 hours](#pausing-after-24-hours-stand-by)).
8. **No real people in copy.** Examples use generic situations. We don't put a real private
   person's name (for example a family member) in UI copy or in the repo.

---

## Modes

| Mode | Windows | UI labels |
|---|---|---|
| `OFF` (default) | none | panel hidden |
| `3-BLOCK` | Morning 06:00–12:00, Afternoon 12:00–18:00, Evening 18:00–24:00, each clipped to active hours; a block entirely outside active hours is skipped | `MODE: 3-BLOCK · NEXT BLOCK: AFTERNOON (12:00–18:00)` |
| `HOURLY` | every whole local hour inside active hours | `MODE: HOURLY · NEXT CHECK-IN DUE: 14:00` |

- Windows are wall-clock hours in the player's `time_zone`, so DST days simply have one fewer or
  one more window. Timestamps are stored in UTC.
- A window is satisfied by one check-in inside it. A check-in up to 10 minutes after the window
  ends counts as `late` (not missed). Later than that, the window is `missed`.
- One check-in per window. A second one in the same window returns 409.

### Status

| Status | Meaning | Label colour (always with text) |
|---|---|---|
| `ok` | current window satisfied, or not yet in its last 10 minutes | green |
| `approaching` | last 10 minutes of an unsatisfied window | amber |
| `overdue` | window ended, inside the 10-minute late grace | amber |
| `non_compliant` | a recovery task is open (see [Recovery task](#recovery-task-assignment)) | red, `NON-COMPLIANT` |
| `exemption_active` | an exemption covers now | cyan, `EXEMPTION ACTIVE` |
| `stand_by` | paused after 24h with no check-in; nothing accrues | muted, `STAND-BY` |

Precedence when several apply: `exemption_active` > `stand_by` > `non_compliant` > `overdue` >
`approaching` > `ok`.

### Pausing after 24 hours (STAND-BY)

- **Trigger.** Let `anchor` = the latest of `last_checkin_at`, the time check-ins were last
  switched on (`checkin_state.enabled_at`), and the end of the last exemption. When
  `now − anchor ≥ 24h`, the layer is in `stand_by`. It is a computed state, not a stored flag;
  `standby_since` (= `anchor + 24h`) is written only so the next visit can show the re-entry
  briefing once.
- **What is logged.** Windows that ended in the first 24h after `anchor` are logged `missed` as
  usual, so a long absence costs at most one day of misses. Windows after `anchor + 24h` are not
  logged at all. They are not missed, they don't enter the compliance denominator, and they don't
  raise the voice level.
- **During stand-by:** no drill lines, no new recovery task, no further lock. A recovery task
  already open stays open (still one task).
- **Exit.** Any check-in ends stand-by and becomes the new `anchor`; the next window is judged
  normally. Switching check-ins off and on also resets `anchor`. The re-entry briefing is neutral
  copy (`STAND-BY ENDED · Resume at the next window.`); the voice speaks only if a recovery task is
  open.

### Lazy evaluation (no scheduler)

Status is computed on request. `checkin_state.evaluated_through` records how far windows have
been judged. On each status, check-in or dashboard request, the service walks the windows that
ended (plus grace) since then, up to 24 hours of them, and writes a `checkin_log` row with status
`missed` or `exempted` for each window that had no check-in. `checkin_log` is unique on
`(user_id, window_start)`, so concurrent requests can't double-count a miss. This is the same
pattern as `daily_plans`.

---

## Check-in and progress report

`POST /api/checkin` records `checked_in_at` (server time; the client never supplies it) and
auto-fills, for the period since the previous check-in:

- `missions_completed`: from mission completions / `MissionLog`.
- `words_reviewed`, `words_new`: from review events and `vocab_progress` (zero until the
  language-focus increment lands).
- `notes`: optional, ≤ 500 characters. Shown only to the player. Never fed to the recruiter.

Dashboard lines:
- `Last check-in: 23 min ago · 3 missions, 42 reviews, 15 new words`
- `Last block: MORNING · 2 missions, 1 language pack, 60 reviews`

---

## Penalties for missed check-ins

These are the options chosen from the brief:

| Penalty | Decision |
|---|---|
| **Status penalty** | Yes. `CHECK-IN STATUS: NON-COMPLIANT · Last check-in: 3h 10m ago` in red, with the text label. |
| **Temporary lock on non-essential features** | Yes, until the recovery task is done. Non-fitness missions show `LOCKED · RECOVERY REQUIRED`; starting or completing one returns 409 `recovery_required`. Surge packs and optional challenges are locked. Streaks and badges are **frozen** (dimmed, not reset) and resume afterwards. |
| **Recovery task** | Yes. See below. |
| **Permanent pace penalty** | **No.** Missed windows are recorded permanently in compliance metrics, which is honest, but they don't lower the mission and word "expected pace" curves. A permanent pace hit can't be recovered from, and it would mix two different measures into one number. |
| **Recruiter narrative** | Yes, in-fiction, through the discipline voice below. |

### Recovery task assignment

**Fixed size, adaptive content.** The task is always 10 minutes and never grows with the number
of misses or the voice level. The voice level changes only the copy around it. What the ten
minutes are spent on adapts to the player:

| Condition | Task `kind` | Content |
|---|---|---|
| Language focus is live and some language has focus words | `focus_session` | The language with the most focus-list words; ties go to the most negative lexicon pace delta, then the order ar, fa, he. Reuses the focus drill. |
| Otherwise | `study_debrief` | A 10-minute timed session on today's study mission (or the most recent one), then a three-line written debrief. |

**When one is assigned.**
- A task is assigned when a window is logged `missed` and no task is open. Assignment is part of
  the same lazy evaluation that writes the `missed` row.
- **At most one open task** (partial unique index). More misses while it is open are logged and
  count toward compliance and the voice level, but add nothing to the task.
- **At most one task per local day.** A miss after that day's task was completed is logged, and
  the panel shows `Missed 14:00 window (logged)`, but there is no new lock until the next local
  day. This keeps hourly mode from locking the player again and again in one day.
- None during an exemption or stand-by. Switching check-ins off closes any open task.

**Completion.**
- The server measures duration from its own `started_at` / `completed_at`. The client can't
  shorten it. A `study_debrief` also needs a non-empty debrief.
- Completing the task clears `non_compliant`, lifts the lock and unfreezes streaks, however many
  windows were missed.

---

## Emergency exemption

A rate-limited action, confirmed in a modal. It isn't a secret code: anything shipped to the
browser is public, and a server-side code the player already knows is equivalent to a button.

- **Limit:** 5 per 90-day programme. One active at a time.
- **Input:** `exemption_hours`, an integer from 2 to 8; `reason`, optional, ≤ 200 characters.
  The reason is never judged, scored or quoted by the recruiter.
- **Backdating:** the exemption may start at the beginning of the current unsatisfied window, if
  that window started less than 2 hours ago. This covers "the emergency started before I could
  open the app" without allowing a long history to be erased.
- **Effect:** windows inside `[starts_at, ends_at)` are logged `exempted`. No penalties and no
  discipline voice during the window.
- **UI copy:**
  - `EXEMPTION ACTIVE: 2h 30m remaining. No penalties during this window.`
  - `Emergency exemption uses remaining: 2/5`
  - `This is for genuine emergencies only — for example childcare, a family or medical
    emergency, or work you can't step away from.`
- **Out of exemptions:** check-ins can still be switched off in Settings (Guardrail 3). Running
  out never traps the player.

---

## Data & logic requirements

**`checkin_state`** (1:1 with `users`; `user_id` is the PK and FK, ON DELETE CASCADE):

| Column | Type | Rule |
|---|---|---|
| `checkin_mode` | `str_enum(CheckinMode)`: `off`, `block`, `hourly` | default `off` |
| `active_start`, `active_end` | `Time` | default 08:00 / 22:00; CHECK span 1–16 h |
| `voice_intensity` | `str_enum(VoiceIntensity)`: `off`, `moderate`, `full` | default `moderate` |
| `last_checkin_at` | `DateTime(tz)`, nullable | |
| `last_block_checked` | `str_enum(Block)`: `morning`, `afternoon`, `evening`, nullable | |
| `evaluated_through` | `DateTime(tz)`, nullable | lazy-evaluation watermark |
| `exemption_uses_remaining` | `SmallInteger`, default 5 | CHECK 0–5 |
| `current_exemption_until` | `DateTime(tz)`, nullable | |
| `missed_checkins_count`, `missed_blocks_count` | `SmallInteger`, default 0 | lifetime totals; CHECK ≥ 0 |
| `enabled_at` | `DateTime(tz)`, nullable | when check-ins were last switched on (stand-by anchor) |
| `standby_since` | `DateTime(tz)`, nullable | `anchor + 24h`; for the one-time re-entry briefing |

**`checkin_log`**: `id`, `user_id` (FK cascade), `window_start`, `window_end`,
`checked_in_at` (nullable for missed/exempted), `mode`, `block` (nullable),
`missions_completed`, `words_reviewed`, `words_new` (`SmallInteger` ≥ 0), `notes` (Text, ≤ 500),
`status` (`on_time`, `late`, `exempted`, `missed`). Unique `(user_id, window_start)`. Index
`(user_id, window_start)`. Rolling 7-day miss counts are queries over this table. The lifetime
counters in `checkin_state` are caches.

**`exemption_log`**: `id`, `user_id` (FK cascade), `used_at`, `starts_at`, `ends_at`,
`exemption_hours` (CHECK 2–8), `reason` (≤ 200, nullable).

**`recovery_tasks`**: `id`, `user_id`, `assigned_at`, `kind` (`focus_session`,
`study_debrief`), `language` (nullable), `voice_level` (0–3, for copy), `started_at`,
`completed_at`, `debrief` (nullable). A partial unique index allows one open task per user.

**API** (all require login and filter by `current_user.id`; Pydantic in and out):

| Endpoint | Body | Returns / effect |
|---|---|---|
| `GET /api/checkin-status` | — | `mode`, `last_checkin_at`, `next_checkin_due_at`, `current_block`, `status`, `exemption_uses_remaining`, `exemption_until`, `missed_checkins_count`, `missed_blocks_count`, `missed_7d`, `voice_level`, `voice_line` (nullable), `recovery_task` (nullable) |
| `POST /api/checkin` | `{notes?: str ≤ 500}` | 201 with the log row; 409 if this window is already satisfied or mode is `off` |
| `POST /api/exemptions` | `{exemption_hours: int 2–8, reason?: str ≤ 200}` | 201; 422 out of range; 409 if none remaining or one is active. Decrements uses and logs, in one transaction with a row lock on `checkin_state`. |
| `GET/PATCH /api/checkin-settings` | `{checkin_mode?, active_start?, active_end?, voice_intensity?}` | Switching to `off` clears the lock and open recovery task. |
| `POST /api/recovery-tasks/{id}/start`, `/complete` | `{debrief?}` | Completion checks at least 10 minutes by server clock. |

Logic lives in `app/services/checkins.py`. Window maths and status are pure functions of
`(settings, now, logs, exemptions)`, testable without a database, like `select_templates`.

---

## Dashboard integration

Panel **`STATUS // CHECK-INS`**, directly under the top bar when check-ins are enabled:

```
┌─ STATUS // CHECK-INS ─────────────────────────────────────────────────────────────┐
│ MODE: HOURLY · NEXT CHECK-IN: 14:00           STATUS: OK                           │
│ Last: 23 min ago · 3 missions, 42 reviews, 15 new words                            │
│ Exemption uses remaining: 2/5                                                      │
│ [ CHECK IN NOW ]   [ USE EMERGENCY EXEMPTION ]                                     │
└────────────────────────────────────────────────────────────────────────────────────┘
```

In the non-compliant state:
- A red banner with the text `DISCIPLINE BREACH: You missed your last check-in.` and
  `Required: complete a recovery task before new missions.` Below it, the discipline-voice line
  for the current level (if the voice is on).
- `RECOVERY TASK: Complete a 10-minute focus session (Arabic) to restore operational status.`
  plus a **Complete recovery task** button. It is also Priority Action 1.
- Streaks, badges and optional challenges are dimmed with the text `FROZEN`.
- Under every discipline-voice line: `Voice too harsh? Adjust in Settings.` (a link).

The exemption modal has an hours stepper (2–8), an optional reason, the uses count, the
genuine-emergency copy, and **Confirm**/**Cancel** buttons.

---

## Completion Logging & Metrics

- `checkin_log` is the compliance record: every window ends up `on_time`, `late`, `exempted` or
  `missed`.
### Compliance metric

Over the rolling 7-day window (log rows with `window_start` in `[now − 168h, now)`):

```
compliance_7d = (on_time + late) / (on_time + late + missed)
```

- **Exempted windows are left out of both sides.** They neither help nor hurt. Counting them as
  compliant (the `(on_time + exempted) / total` alternative) would make spending exemptions
  improve the score, which rewards the overuse that the warning lines exist to discourage.
- `late` counts as compliant. It is shown separately (`2 LATE`) but isn't penalised.
- Stand-by and `off` time produce no rows, so they aren't in the denominator.
- If the denominator is 0, the metric is `null` and the UI shows `COMPLIANCE 7D: —`.
- It is shown as its own metric (`COMPLIANCE 7D: 86%`) and is **never** folded into expected
  pace.
- `missed_7d` (missed windows) and `missed_blocks_7d` (see
  [Intensity levels](#intensity-levels)) drive the discipline-voice level.
- Recovery task completions are logged with duration.
- Check-in auto-fill reads the same sources as the dashboard, so the numbers always agree.

---

## Planner integration

- **Selection doesn't change.** `select_templates` never sees check-in data. The lock is applied
  when missions are served and started, not when they are chosen, so re-enabling doesn't
  re-plan anything.
- **Recruiter facts** (structured, no free text):
  `{"missed_7d": 3, "missed_blocks_7d": 1, "compliance_7d": 0.82, "perfect_days_streak": 0}`.
- **Missed 3 or more this week:** discipline-voice narrative and a recovery task. **No harder
  missions and no fewer hints.** Making the work harder when someone is struggling to show up
  compounds drop-out, and it would punish learning for a scheduling problem. That option from the
  brief is deliberately not taken.
- **Seven perfect days:** positive handler line and an optional, unscheduled bonus (a surge pack
  or a bonus fictional scenario). A bonus is never required.

---

## Tone & Framing Notes

- Vocabulary: check-in window, compliance, breach, recovery task, exemption, stand down,
  operational status. Never homework, detention, punishment or "grounded".
- The point is operational reliability, not punishment for its own sake. Neutral widgets state
  facts. Only the discipline voice (below) is harsh, and only in the situations listed there.
- Example neutral copy:
  - `CHECK-IN STATUS: NON-COMPLIANT · Last check-in: 3h 10m ago.`
  - `Recovery required before new missions.`
  - `Exemption active: 2h 30m remaining. No penalties during this window.`

---

## Maximum-Intensity Drill-Sergeant Voice (Female, Non-Compliance Only)

### Voice identity

An in-fiction female handler, call sign **KESTREL**, part of the MIDRASHA scenario. She is hard
and direct, with no sugar-coating. She talks about commitment, reliability, discipline, and the
gap between what the recruit said they'd do and what they did.

**She speaks only for:** missed hourly windows, missed blocks, repeated non-compliance, recovery
task assignments, and exemption-overuse warnings.

**She never speaks:** during an active exemption; about exempted windows; about fitness results;
on on-track status, tutorials, or neutral explanations (those stay professional and neutral);
when check-ins are `off`.

### Content rules

**The line:** attack the behaviour and the gap between words and actions. Never the person's
worth or identity.

- **Allowed:** missed windows, broken commitments, follow-through, excuses, the record this
  week, what an operator would do next.
- **Hard exclusions:** body, appearance, gender, ethnicity, nationality, religion, sexuality,
  disability, age; mental-health diagnoses; family roles ("bad parent"); profanity aimed at the
  player; threats of real-world harm or consequences; anything saying the player is worthless or
  hopeless, or telling them to give up; doubting that an emergency was real.
- **Every harsh line ends pointing at the next action** (the next window or the recovery task).

### Intensity levels

Computed from `checkin_log` over the same rolling 7 days as the compliance metric. Exempted
windows and stand-by time never count.

- `missed_7d`: windows logged `missed`.
- `missed_blocks_7d`: missed whole blocks. In 3-block mode, a missed block window. In hourly
  mode, a block (morning, afternoon or evening, clipped to active hours) whose windows were
  **all** missed.

| Level | Hourly mode | 3-block mode | Register |
|---|---|---|---|
| 0 Compliant | 0 missed | 0 missed | neutral copy only |
| 1 First miss | 1 missed window | 1 missed block | direct, no coddling |
| 2 Repeated | 2–3 missed windows, 0–1 missed blocks | 2 missed blocks | harsher; names the gap between words and actions |
| 3 Chronic | 4+ missed windows, or 2+ missed blocks | 3+ missed blocks | maximum intensity, within the content rules |

A block is six times the commitment of an hourly window, so the 3-block thresholds count blocks.
Level 3 still needs a repeated pattern, not one bad day. The level only goes down as misses age
out of the 7-day window. A recovery task clears the lock, not the record.

**Setting: Discipline voice intensity**
- `Off`: neutral copy only, whatever the level.
- `Moderate` (default): capped at level 1.
- `Full`: all levels. Selecting `Full` shows: *"This voice is intentionally harsh. If it's too
  much, reduce the intensity in Settings."* The player confirms.

Displayed level = `min(computed level, cap)`. The computed level is still sent to the recruiter
as a fact.

### Lines

Copy lives in `prompts/recruiter/discipline_lines.json`, as entries of `{id, level, context,
text}`, where `context` is `missed_window`, `missed_block`, `recovery_task` or
`exemption_overuse`. Selection is deterministic: seeded by user and date, and not repeated
within 3 days. The table below is the starting set. I've accepted most of the brief's lines
verbatim. The ones marked ✎ are rewritten because they judged the person, not the behaviour.

| Level | Context | Line |
|---|---|---|
| 1 | missed_window | "You missed your check-in. Don't pretend it's nothing. You said you were in. Show me at the next window." |
| 1 | missed_window | "One missed check-in. That's a mark. You decide if it's a pattern." |
| 2 | missed_window | "Two missed check-ins already. That wasn't 'busy'; that was unfocused. Operators don't beg for time; they take it and use it." ✎ |
| 2 | missed_window | "You keep saying you're serious. Then act like it. Hit the next check-in." |
| 2 | missed_window | "Third miss this week. You're not forgetting; you're choosing. Choose differently at the next window." |
| 3 | missed_window | "Three days like this and you're still surprised it's not working? Weak follow-through, weak results. Fix the follow-through." |
| 3 | missed_window | "You want the outcome without the discipline. That's not how this works. Either you show up at the next window or you don't." |
| 3 | missed_window | "This isn't 'life getting in the way' any more. This week's record reads unreliable and unfocused. Records change when behaviour changes. Start now." ✎ (was: "This is you showing me who you are … Not operator material.") |
| 3 | missed_window | "Your actions this week say you don't want this. Prove them wrong at the next window." ✎ (was: "You keep proving you don't actually want this. Fine. Act accordingly.") |
| 2 | missed_block | "A whole block gone. You didn't 'forget'. You chose something else. Own that, then own the next block." |
| 3 | missed_block | "You let the whole block slip. Morning, afternoon, evening: pick one and own it. Right now you own none of them." ✎ (was: "you own nothing") |
| 1–3 | recovery_task | L1: "Recovery task. Ten minutes, focus session. Do it and you're back in." L2: "You want back in? Fine. Complete this recovery task. No drama, no excuses." L3: "This is the price of admission. Ten minutes, your weakest language. Pay it and prove you can follow one simple order." |
| 2–3 | exemption_overuse (≤ 1 use left) | "One exemption left. If these were real emergencies, that's what they're for; handle them first. If they weren't, stop spending them. You'll want that last one when it counts." ✎ (was: "Either you're in crisis, or you're treating this like a game …") |

Why the ✎ changes:
- "Not operator material" and "you keep proving you don't want this" are verdicts on who the
  player is, which the brief's own rule forbids.
- "Fine. Act accordingly" can read as permission to quit.
- The exemption-overuse line must never suggest a real emergency was fake. That would push
  people to skip exemptions they genuinely need.

**Audio (optional, later):** a female voice from a free/open-source TTS engine (for example a
female Piper or espeak-ng voice), enabled only after it has an entry in the per-voice licence
register (see [language-focus.md](language-focus.md#tts-and-voice-licences)). It never
auto-plays.

### Tests

- `test_drill_voice_intensity_levels`: hourly mode, 0, 1, 2–3 and 4+ missed windows and 2 missed
  blocks map to levels 0, 1, 2, 3, 3; 3-block mode, 0, 1, 2 and 3+ missed blocks map to 0, 1, 2,
  3; each picks lines of that level.
- `test_drill_voice_off_setting`: with `Off`, no drill line appears even at level 3.
- `test_drill_voice_moderate_caps_at_level_one`.
- `test_drill_voice_silent_during_exemption`.
- `test_drill_voice_targets_behaviour_not_identity`: every line in `discipline_lines.json` is
  checked against banned-term lists (protected characteristics, body, diagnoses, family roles,
  profanity, threats) and against identity-verdict patterns (`you are/you're (a )?(worthless|
  hopeless|failure|loser|pathetic|lazy|stupid|…)`). Every line must mention a next action. This
  is a floor, not proof: every copy change also gets human review.
- `test_recovery_task_copy_matches_non_compliance_level`.

### Ethics & Safety

- The discipline voice is fictional and scenario-based. KESTREL is a character, not a judgement
  from the app's authors.
- It targets behaviour (check-ins, follow-through), never identity or worth.
- The player chooses the intensity and can turn it off, or switch check-ins off entirely, at any
  time, with one setting and no penalty for doing so.
- The system doesn't encourage self-harm, dangerous behaviour, sleep loss or neglecting
  real-life responsibilities: there are active hours only, no overnight windows, no fitness
  penalties, and exemptions for genuine emergencies (childcare, family or medical emergencies,
  work).
- **If a player reports distress, the answer is to reduce the intensity or turn the voice off,
  not to "tough it out".** Settings show this, and so does the first-run explanation screen,
  next to a plain line: "If this is affecting how you feel outside the game, stop and talk to
  someone you trust."
- Check-in notes and exemption reasons are private to the player. They are never analysed,
  scored or shown to the recruiter.

---

## Tests (check-in layer)

Test-first, in `tests/test_checkins.py` (pure window/status functions first, then API):

- `test_hourly_checkin_enforced`: over an hour with no check-in → `overdue`, then after grace
  `non_compliant`.
- `test_block_checkin_enforced`: a missed block → `missed` row and a recovery task.
- `test_emergency_exemption_prevents_penalty`: a 3-hour exemption → windows `exempted`, status
  never `non_compliant`, no drill line.
- `test_exemption_uses_limit`: a 6th exemption → 409; 1 or 9 hours → 422.
- `test_checkin_records_progress`: auto-fills missions, reviews and new words since the last
  check-in.
- `test_recovery_task_required_after_missed_checkin`: starting a non-fitness mission → 409 until
  recovery completes; fitness still works.
- `test_dashboard_shows_non_compliant_status` (frontend): the banner text `NON-COMPLIANT` renders,
  not only red.
- Also:
  - `test_no_windows_outside_active_hours`
  - `test_missed_windows_are_idempotent` (concurrent evaluation writes each miss once)
  - `test_standby_after_24h_silence` (at most 24h of misses logged; none after; check-in exits)
  - `test_compliance_excludes_exempted_windows` (and `null` with no judged windows)
  - `test_recovery_task_is_fixed_length_and_picks_most_focus_words`
  - `test_at_most_one_recovery_task_per_local_day`
  - `test_turning_checkins_off_clears_lock`
  - `test_recovery_is_not_shorter_than_ten_minutes`
  - `test_other_users_checkins_are_404`

## Free / open-source constraints

- Plain server-side state and timestamps; no cron, queues, push services or third-party timers.
- The frontend is plain React and the existing CSS. The countdown reuses `useCountdown`.
- No analytics, telemetry or proprietary components.
