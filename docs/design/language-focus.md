# Language Focus — design

**Status:** approved design, not built. Increment #7b (after the dashboard). The bulk vocabulary
content is a separate content stream, not part of the code increment.

Related: [dashboard.md](dashboard.md), [checkins.md](checkins.md), [PRD](../PRD.md).

---

## Mission type

New enum value `MissionType.LANGUAGE_FOCUS = "language_focus"`.

| | `language` (existing) | `language_focus` (new) |
|---|---|---|
| Purpose | Skills: script, listening, code-switching, drills (increment 7) | Domain vocabulary for reading conflict and intelligence reporting |
| Languages | Often several per mission | Exactly one per mission |
| Content | Free-text task | A versioned vocab pack plus SRS review |
| Progress | Completed or not | Per-word memory state (FSRS) |
| Scheduling | Freshness / least recently used | Curriculum order in Induction and Specialisation; adaptive in Operations |

**New nullable `MissionTemplate` columns** (in the language-focus migration, after 0003):

| Column | Type | Rule |
|---|---|---|
| `language` | `str_enum(FocusLanguage)`: `ar`, `fa`, `he` | required for `language_focus` |
| `domain` | `str_enum(FocusDomain)`: `core`, `military`, `terrorism`, `religion`, `politics` | required |
| `secondary_domains` | `StringArray` | Operations mixed packs only |
| `subdomain` | `String(60)` | required |
| `sequence` | `SmallInteger`, 1–60 | required; curriculum position within the language |
| `word_count` | `SmallInteger`, 1–200 | required |
| `content_path` | `String(200)`, relative to `db/seeds/` | required |
| `estimated_hours` | `Numeric(3,1)` | required |

- A CHECK constraint `language_focus_fields` requires all of the above when
  `type = 'language_focus'`.
- The migration must drop and recreate the `mission_type` CHECK constraint to add the new value.
- Catalogue `key` becomes the uuid5 id, and `name` is the title, as for other templates.

**Missions per day.** One `language_focus` mission a day, in its own slot, rotating
ar → fa → he. Add `Slot((LANGUAGE_FOCUS,))` to every phase; the generic `language` slot stays.

- The focus mission also runs that day's SRS reviews for **all three** languages. New words
  arrive one language at a time, but every language gets contact every day.
- Why one slot rather than three: three new-word sessions a day, on top of fitness, study and
  OSINT, is not a realistic load for a zero-knowledge player.

---

## Vocabulary targets (honest numbers)

| Phase | Days | Scheduled packs (1 in 3 days) | Words per pack | Introduced by the schedule | Catalogue packs incl. surge | Catalogue words |
|---|---|---|---|---|---|---|
| Induction | 1–21 | 7 | 60 | 420 | 10 | 600 |
| Specialisation | 22–60 | 13 | 100 | 1,300 | 22 | 2,200 |
| Operations | 61–90 | 10 | 110 | 1,100 | 20 | 2,200 |
| **Total** | | **30** | | **≈ 2,820** | **52** | **5,000** |

- **The schedule introduces about 2,820 words per language.** That is the expected pace.
- **5,000 is a target, reachable only with optional surge packs.** The planner never
  schedules surge packs; the player asks for them.
- With daily reviews, expect roughly 60–70 % of introduced words to be "known" at any time.
- **Never label the outcome as CEFR B2** (or any CEFR level). CEFR levels describe skills, not
  word counts. Use "operational reading of domain reporting".
- Time: about 25 minutes a day in Induction, rising to 45–60 minutes in Operations as reviews
  accumulate.

---

## First-release scope (content limits)

The first vocabulary release covers **only** these areas:

| Area | Subdomains in release 1 |
|---|---|
| Reporting language (`core`) | news syntax; numbers, dates, places; reporting verbs (claimed, confirmed, denied); attribution and hedging |
| Source reliability (`core`) | source grading, corroboration, rumour vs confirmation, official vs anonymous sourcing |
| Chronology (`core`) | timelines, sequence, before/after, duration, date formats in each calendar in press use |
| Institutions (`politics`, `religion`) | state_government, courts and prosecutors, religious institutions, clergy_authority |
| Politics | parties_elections, coalition_cabinet, diplomacy_ceasefire, sanctions_economy, foreign_policy |
| Religion | institutions, practice_calendar, holy_sites, religion_and_state (institutional literacy only) |
| Ranks and structure (`military`) | ranks_units, forces_structure, ranks_acronyms (he) |
| Incident and legal reporting (`terrorism`) | incident_reporting (how the press reports an event), arrests_courts, counterterror_policy |

**Excluded from release 1:**

- Procedural attack or tactical vocabulary, and weapon vocabulary of any kind. The earlier
  `weapons_categories` subdomain is dropped.
- Extremist-content vocabulary: slogans, propaganda terms, claims language. The earlier
  `claims_propaganda_terms` subdomain is dropped.
- `proxies_intelligence`, `operations_movement`, `logistics_supply`, `intel_recon` and
  `casualties_damage`. These are deferred until a content review decides whether and how they
  can be written as reporting vocabulary only.

Curriculum order per language follows this scope: `core` packs first, then ranks/structure and
institutions, then politics and religion, with incident/legal reporting from Specialisation on.
Operations packs are mixed-domain (for example religion + politics) drawn from the same scope.

---

## Word-list files

Files live at `db/seeds/vocab/{lang}/{domain}/{subdomain}.json`. The backend serves them through
`GET /api/vocab/{pack_key}`, which requires login and validates with Pydantic. They are not
static files.

Required pack fields: `pack_key` (`^lf-(ar|fa|he)-[a-z0-9-]+$`), `language`, `domain`,
`subdomain`, `version`, `license`, `entries` (1–200).

Required entry fields: `id` (`^(ar|fa|he)-[a-z]{3}-[0-9]{4}$`, stable forever, because progress
is keyed on it), `term` (unvocalised, as printed), `translation`, `pos`, `example`
(`{text, translation}`), `tags`, `source` (`original` or `wiktionary:<page>`).

Optional entry fields: `term_vocalized` (harakat/niqqud, fed to TTS), `transliteration`,
`gender`, `plural`, `root`, `register`, `note`.

Rules:
- Example sentences are set in the fictional setting (Port Venn, the Orchard Circle).
- No real armed or extremist group names in entries or examples.
- A native-speaker reviewer checks every pack before it ships.
- Audio is not stored in packs (see TTS below).

---

## Planner Integration (Language Focus)

This extends the planner; nothing is rewritten.

1. **Enum and ordering.** Add `LANGUAGE_FOCUS` to `MissionType`, and to `TYPE_ORDER` right after
   `LANG`. Without the `TYPE_ORDER` entry, `missions_on` raises.
2. **Slots.** Add `Slot((LANGUAGE_FOCUS,))` to all three `PhaseRule`s.
3. **History.** Extend `PlayerHistory`, keeping `select_templates` pure:
   - `focus_assigned: Counter[str]`: language → focus packs assigned before `on_date`.
   - `known_share: dict[tuple[str, str], float]`: (language, domain) → known ÷ introduced, from
     `vocab_progress`.
4. **Ranking for the focus slot only**, most important first: pinned; freshness; language
   balance (`focus_assigned[lang] / weight(lang)`); rotation order ar, fa, he; then
   - Induction and Specialisation: `sequence` (a fixed curriculum);
   - Operations: weakest known share across the pack's domains, then mixed-domain packs first,
     then difficulty nearest **that language's** level + 1, then `sequence`.

   The existing `rank` stays as it is for every other slot. `weight()` is 1 for every language
   until a "language emphasis" setting exists.
5. **Surge packs are never scheduled.** They have no phase eligibility for the planner.
6. **Catalogue validation** already rejects pinned templates that can't be scheduled; the focus
   slot is covered automatically.
7. **Check-ins.** Recovery tasks are focus sessions, not planned missions (see
   [checkins.md](checkins.md#planner-integration)).

Tests first: languages rotate evenly over 90 days; curriculum order before Operations; Operations
prefers the weakest domain and mixed domains; per-language level drives difficulty; `missions_on`
orders `language_focus`; surge packs never appear in a plan.

---

## Completion Logging & Metrics

**Per-word state: `vocab_progress`.**
- Columns: `user_id` (FK, cascade), `entry_id String(16)`, `language`, `domain`, `pack_key`, the
  FSRS fields (`state`, `stability`, `difficulty`, `due`, `last_review`, `reps`, `lapses`), plus
  `last_rating`, `mistake_count` (≥ 0), `last_wrong_at`, `correct_streak`.
- Unique on `(user_id, entry_id)`; index `(user_id, language)`. Every query filters by
  `current_user.id`.
- Reviews arrive as `POST /api/vocab/reviews`: a batch (≤ 500) of
  `{entry_id, rating: 1-4, reviewed_at, source: srs|focus|quiz|mission}`. The **server** runs
  FSRS; client figures are never trusted. A wrong answer is rating 1.

Definitions: **introduced** = a row exists; **known** = stability ≥ 7 days and last rating Good
or Easy; **mature** = stability ≥ 21 days.

**One scheduler.** There is a single py-fsrs `Scheduler` with one desired retention for every
word. Mistakes are prioritised by **queue ordering only**, not by a second scheduler:

- Focus-list membership is derived: `mistake_count > 0` and not (`correct_streak ≥ 3` and
  `stability ≥ 21`).
- Daily review order: `(in_focus desc, mistake_count desc, due asc)`.
- Focus session queue: focus-list words, due or not, ordered by
  `(mistake_count desc, last_wrong_at desc)`, limit 20 cards or 10 minutes. Early review is
  normal in FSRS, which accounts for elapsed time.

**Completion log.** When the template is `language_focus`, the server fills
`MissionLog.metrics` at completion from `vocab_progress` (never from the client): `pack_key`,
`language`, `domain`, `words_in_pack`, `words_introduced`, `words_known_in_pack`,
`reviews_done`, `review_accuracy` (0–1), `minutes_active` (0–600).

**Check-in auto-fill.** A check-in counts reviews (`reviews_done` source rows) and newly
introduced words since the previous check-in from `vocab_progress` / the review events. See
[checkins.md](checkins.md).

**Recruiter facts.** A `LanguageProfile` per (language, domain): coverage = known ÷ scheduled to
date; strong ≥ 0.7, developing 0.4–0.7, weak < 0.4. The recruiter receives structured facts
only. Weaknesses are training targets, never shaming.

---

## TTS and voice licences

- **Every TTS model and every voice is licensed separately.** A voice is not enabled until it
  has an entry in a licence register (planned: `docs/licences/tts-voices.md`) with: engine and
  version, voice id, model card URL, licence of the model weights, licence/provenance of the
  training data, commercial use allowed (yes/no), attribution text, and date checked.
- Engine code licences (for example Piper MIT / `piper1-gpl` GPL-3.0, espeak-ng GPL-3.0) do not
  cover voice models. Check each voice.
- Excluded: any voice whose weights or data are non-commercial or unclear (for example Coqui
  XTTS-v2 under the Coqui Public Model License, Meta MMS-TTS under CC BY-NC 4.0), and every paid
  or cloud TTS.
- **Hebrew audio is optional.** If no Hebrew voice passes the licence check with acceptable
  quality, Hebrew ships without audio.
- Audio is pre-generated offline to `audio/{entry_id}.ogg` from `term_vocalized`, gitignored, and
  built at deploy time. The TTS endpoint runs the engine locally; no third-party API keys.

---

## Tone & Framing Notes

- Frame every pack as a desk task on a fictional file ("Order of battle", "Incident desk",
  "Communiqué desk", "Cabinet room", "Sanctions desk"), ending in an analytic output.
- No travel, shopping or "learn X in Y days" framing.
- Say "operational reading of domain reporting". Never "B2" or any CEFR label.
- Registers: Arabic MSA (press/official); Farsi formal Tehrani press; Hebrew modern press and
  military register, including acronyms. Dialects are out of scope.
- Terrorism-domain vocabulary covers how events are reported, investigated, prosecuted and
  financed. No methods, tactics, instructions, weapons, slogans or propaganda; nothing harvested
  from extremist material.
- Religion is institutional and political literacy. Descriptions never equate faith with threat.
- Check-in and discipline copy follows [checkins.md](checkins.md#tone--framing-notes).

## Free / open-source tooling

| Tool / source | Use | Licence |
|---|---|---|
| py-fsrs | Server-side scheduling (one scheduler) | MIT |
| ts-fsrs (optional) | Client preview of intervals | MIT |
| genanki (optional) | `.apkg` export | MIT |
| Piper / espeak-ng | Offline TTS engines | see TTS section: per-voice register |
| CAMeL Tools (ar), Hazm (fa) | Authoring checks | MIT; check each data package |
| Wiktionary via kaikki.org | Checking glosses | CC BY-SA 4.0 (share-alike if copied) |
| Tatoeba | Optional examples | CC BY 2.0 FR / CC0 subset |
| Noto Sans Arabic / Hebrew, Vazirmatn | Fonts | SIL OFL 1.1, self-hosted |

Nothing here depends on a paid or proprietary service. The real cost is writing and
native-reviewing the content.
