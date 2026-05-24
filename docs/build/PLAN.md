# Jaromelu Build Plan

This document holds active and historical plan docs that drive the persistent task queue in [TASKS.md](./TASKS.md). Plans are written by the `planner` agent (or a planning session) and consumed by the `implementer`.

## What good looks like

A good plan doc is:

- **Self-contained** — readable cold by an implementer with no prior conversation context.
- **Interface-level** — names file paths, types, function signatures, table columns, API shapes, env vars. No "figure out the right shape".
- **End-to-end verifiable** — explicit "how do we know this is done" strategy, runnable from the outside (curl, CLI, screenshot, query).
- **Iterated to high quality** before any task is appended. A plan that ships fuzzy tasks burns implementer time on re-asking.

Plans link to the tasks they spawn. Tasks link back to the plan section they implement.

---

## Active plan

## 2026-05-24: Scout Phase 2.5 closure — SC teams + settings

**Goal:** Take `scout/supercoach_teams/` and `scout/supercoach_settings/` from "code shipped, untested, unscheduled, S3 seeded ad-hoc on 2026-05-12" to **charter-compliant, scheduled, S3-seeded, Shipped** — matching the discipline already in place for `supercoach_roster/` (Phase 1) and `supercoach_stats/` (Phase 2).

**Constraints:**

- Charter D8 (strict-parse + fixture drift tests): every Scout module ships with `tests/fixtures/scout/<pipeline>/canonical_response.json`, strict Pydantic models (`extra='forbid'`), a fixture-mode unit test, and an env-flagged (`SCOUT_DRIFT_LIVE=1`) live-mode integration test that hits the real endpoint. No exceptions for the small siblings.
- Charter D9 (folder layout) — already satisfied; do not refactor.
- Charter D10 (S3-first) — already satisfied; the route writes raw JSON to S3 before DB.
- Charter D13 (DB extractors downstream) — settings writes `sc_settings` via the route. Teams patches `teams.metadata_json.supercoach` via the route.
- META: `make migrate` is the only path to apply migration 055 (already applied per "verified current state").
- META: session-scoped staging — implementer must `git add` only files this task created/modified.
- Cron lives in `scripts/cron.d/jeromelu` (installed to `/etc/cron.d/jeromelu` by `scripts/lightsail-deploy.sh`). Wrappers live in `scripts/scout-refresh.sh` pattern. The implementer must extend the wrapper or add a sister script — **do not** hand-edit the deployed crontab.
- Roadmap acceptance for Phase 2.5 closure: *"Run once with current season → S3 archive is complete for the SC surface."* Includes weekly forward-cron schedule.

**Interface:**

### Files created (per pipeline)

For `supercoach_teams`:

1. `tests/fixtures/scout/supercoach_teams/canonical_response.json` — **full** captured response (17 teams, ~3KB). Capture command: `curl -s "https://www.supercoach.com.au/2026/api/nrl/classic/v1/teams" > tests/fixtures/scout/supercoach_teams/canonical_response.json`. Pretty-print with `python -m json.tool` for diff readability.
2. `tests/unit/api/scout/test_supercoach_teams_models.py` — templated **exactly** on `tests/unit/api/scout/test_supercoach_roster_models.py`. Four cases:
   - `test_canonical_fixture_parses` — every team parses through `SuperCoachTeam`, expect `len(parsed) == 17`, expect all 17 distinct `abbrev` values, expect every `competition.id == 2` (NRL).
   - `test_unknown_field_on_team_raises` — add `bad["is_new_franchise"] = True`, expect `ValidationError` mentioning `is_new_franchise`.
   - `test_unknown_field_on_nested_competition_raises` — add `bad["competition"]["is_super_league"] = False`, expect `ValidationError` mentioning `is_super_league`.
   - `test_missing_required_field_raises` — `del bad["abbrev"]`, expect `ValidationError` mentioning `abbrev`.
3. `tests/integration/scout/test_supercoach_teams_response_shape.py` — templated on `test_supercoach_roster_response_shape.py`. One test: `test_live_supercoach_teams_shape`, gated on `SCOUT_DRIFT_LIVE=1`. Calls `fetch_supercoach_teams(season=date.today().year)`, parses every row through `SuperCoachTeam`, asserts `16 <= len(teams) <= 18` and `len({t.abbrev for t in teams}) == len(teams)` (no duplicates). Failure message: *"Fix path: review the response, update `app.scout.supercoach_teams.models`, regenerate the fixture under `tests/fixtures/scout/supercoach_teams/canonical_response.json`, commit with a note on what the upstream changed."*

For `supercoach_settings`:

1. `tests/fixtures/scout/supercoach_settings/canonical_response.json` — **full** captured response (~15KB). Capture command: `curl -s "https://www.supercoach.com.au/2026/api/nrl/classic/v1/settings" > tests/fixtures/scout/supercoach_settings/canonical_response.json` then `python -m json.tool` rewrite for diff readability. Rationale for full payload: model only enforces 4 top-level keys, but the fixture is the diff target when drift surfaces inside `game.experts.*` or `game.competitions[*]`.
2. `tests/unit/api/scout/test_supercoach_settings_models.py` — templated on `test_supercoach_roster_models.py`. Three cases:
   - `test_canonical_fixture_parses` — fixture parses through `SuperCoachSettings`. Sanity asserts: `competition`, `content`, `game`, `system` are all dicts; `system["currency"] == "AUD"`; `system["timezone"] == "Australia/Sydney"`.
   - `test_unknown_top_level_field_raises` — `bad["loot_boxes"] = {}` at top level, expect `ValidationError` mentioning `loot_boxes`. (Negates the D8 envelope guard.)
   - `test_missing_required_top_level_raises` — `del bad["game"]`, expect `ValidationError` mentioning `game`.
3. `tests/integration/scout/test_supercoach_settings_response_shape.py` — templated on `test_supercoach_roster_response_shape.py`. **Two** parameterised live tests (`SCOUT_DRIFT_LIVE=1` gated): one for `mode="classic"`, one for `mode="draft"` — because the Makefile / fetcher both support `mode` and the upstream draft endpoint has independent drift risk. Both call `fetch_supercoach_settings(season=date.today().year, mode=mode)` then `SuperCoachSettings.model_validate(raw)`. Failure message: *"Fix path: review the response, update `app.scout.supercoach_settings.models` (top-level envelope only), regenerate the fixture, commit with a note on what the upstream changed."*

### Cron schedule

Add two lines to `scripts/cron.d/jeromelu` immediately after the existing scout-refresh entries (current line 31). Weekly cadence per the README of each module ("Weekly (rarely changes)") and per the roadmap entry ("weekly cadence"):

```cron
# Weekly SuperCoach teams refresh — Mondays 23:30 UTC = Tuesday 09:30 AEST.
# Tiny payload (17 rows, ~3KB). Refreshes teams.metadata_json.supercoach.
30 23 * * 1     ubuntu  /opt/jeromelu/scripts/scout-refresh.sh supercoach-teams

# Weekly SuperCoach settings snapshot — Mondays 23:35 UTC = Tuesday 09:35 AEST.
# ~15KB payload. Captures game rules per season into sc_settings (classic mode).
35 23 * * 1     ubuntu  /opt/jeromelu/scripts/scout-refresh.sh supercoach-settings
```

Extend `scripts/scout-refresh.sh` so the `case "$JOB"` statement (currently `channel-stats|videos`) also accepts `supercoach-teams` (`ENDPOINT="supercoach-teams"`) and `supercoach-settings` (`ENDPOINT="supercoach-settings"`). The script's existing URL template at line 41 (`https://${API_HOST}/api/admin/scout/${ENDPOINT}`) prepends `/api/admin/scout/` automatically, so the ENDPOINT value must NOT include a leading `scout/`. Also update the usage message on line 34 to include the new job names. No other changes — same curl pattern, same loopback `--resolve`, same `--max-time 3600`, same log line format to `/var/log/jeromelu/scout-refresh.log`.

**Why not extend `cron_report.py`:** the existing report already greps `SCOUT_LOG = "/var/log/jeromelu/scout-refresh.log"` and reports per-job status. Adding more jobs to the same log file means they show up in the digest automatically. The report's per-job parsing must be checked against the new job names (see task verification).

**Why classic-only weekly cron, not draft:** roadmap line 44 marks `supercoach_draft_*` as *"🟡 optional — Phase deferred"*. The route accepts `?mode=draft` and the drift test covers it (so we'd know if it broke), but production cron is classic only. Operators can `make scout-supercoach-settings MODE=draft` on demand.

### One-time S3 seed run (post-merge)

After CI passes and the implementer (or human) ships the cron, run once against prod with the current season:

```bash
make scout-supercoach-teams ADMIN_KEY=$ADMIN_KEY SEASON=2026 API=https://api.jeromelu.ai
make scout-supercoach-settings ADMIN_KEY=$ADMIN_KEY SEASON=2026 API=https://api.jeromelu.ai
make scout-supercoach-settings ADMIN_KEY=$ADMIN_KEY SEASON=2026 MODE=draft API=https://api.jeromelu.ai
```

Verify the seed lands by listing the bucket:

```bash
aws s3 ls s3://jeromelu-clean-documents/scout/supercoach/classic/teams/
aws s3 ls s3://jeromelu-clean-documents/scout/supercoach/classic/settings/2026/
aws s3 ls s3://jeromelu-clean-documents/scout/supercoach/draft/settings/2026/
```

Each should show today's-dated keys (teams → `2026.json`; settings → `2026/YYYYMMDD.json`). Verify DB rows:

```bash
make db-shell
=> SELECT season, captured_date, mode FROM sc_settings ORDER BY captured_at DESC LIMIT 5;
=> SELECT slug, metadata_json->'supercoach'->>'abbrev' FROM teams WHERE metadata_json ? 'supercoach' LIMIT 5;
```

`sc_settings` should have the two fresh rows (2026 classic + 2026 draft, dated today). `teams.metadata_json.supercoach` should be populated on all 17 NRL clubs.

**Note:** the 2026-05-12 manual captures already exist in S3 (per `docs/operations/data-sources/supercoach/classic-settings.md`); the seed re-run is to (a) prove the endpoint works end-to-end post-test, (b) refresh stale captures, (c) prove the cron'd job will succeed when it fires.

**Verification strategy:**

- **End-to-end:** `make test` passes in CI (fixture-mode unit tests for both pipelines). `SCOUT_DRIFT_LIVE=1 pytest tests/integration/scout/test_supercoach_teams_response_shape.py tests/integration/scout/test_supercoach_settings_response_shape.py` passes locally before merge. After deploy, the one-time seed runs above complete cleanly. After the first Monday post-deploy, `/var/log/jeromelu/scout-refresh.log` shows two new `[ts] supercoach-teams status=200 ...` and `[ts] supercoach-settings status=200 ...` lines, and the next morning's cron-health email lists both jobs in the digest. The `sc_settings` table grows by one row each week (or stays flat if no upstream change + same-day re-run).
- **Tests:** unit tier under `tests/unit/api/scout/test_supercoach_{teams,settings}_models.py` (drift envelope); integration tier under `tests/integration/scout/test_supercoach_{teams,settings}_response_shape.py` (live drift, env-flagged). No eval tier — deterministic fetchers, per charter "no eval suite for Scout".

**Documentation updates:**

- `docs/agents/crew/scout/roadmap.md` line 58: change Phase 2.5 heading from "Bronze (S3-first) retrofit ✅ + lightweight SC siblings (In design)" to "Bronze (S3-first) retrofit ✅ + lightweight SC siblings ✅". Lines 60–64: change the bullet for `supercoach_teams` and `supercoach_settings` to reflect Shipped status; remove the "Run once with current season" sub-bullet (it's done).
- `docs/agents/crew/scout/charter.md` table at line 42–43: update Status column for `scout/supercoach_teams/` from "🟡 not built — Phase 2.5" to "✅ shipped (Phase 2.5)" and for `scout/supercoach_settings/` from "🟡 not built" to "✅ shipped (Phase 2.5)".
- `services/api/app/scout/supercoach_teams/README.md`: add a "Tests" section pointing to `tests/unit/api/scout/test_supercoach_teams_models.py` and `tests/integration/scout/test_supercoach_teams_response_shape.py`, plus the env-flag instruction.
- `services/api/app/scout/supercoach_settings/README.md`: same, plus a note that the integration test parameterises over `classic` and `draft` modes.
- `scripts/cron.d/jeromelu`: comments above the new lines explaining the cadence rationale (already drafted above; copy verbatim).
- `docs/operations/data-sources/supercoach/classic-teams.md` + `classic-settings.md` + `draft-settings.md`: bump the "Last refreshed" or sample-size line if the seed adds new objects. These are auto-generated by `scripts/profile_s3_json.py` — re-run that script (one command) after the seed.

**Open questions (assumptions ratified 2026-05-24):**

1. **Draft-mode in production cron** — RESOLVED: not needed in cron. Draft is roadmap-deferred and operators can `make` it on demand. Drift test still covers `mode=draft` so the path stays healthy.
2. **Fixture sample size** — RESOLVED: full payload for both (teams = 17 rows, ~3KB; settings = ~15KB). Full is the right diff target since the strict model only enforces top-level keys.
3. **One-time seed who runs it** — RESOLVED: **implementer runs the seed.** TASK-06 reframed accordingly. Requires `ADMIN_KEY` available in the implementer's environment (sourced from `/opt/jeromelu/.env` on Lightsail or equivalent locally). If unavailable, implementer blocks the task rather than improvising.

**Tasks:**

- TASK-01: Add D8 fixture + unit drift tests for `scout/supercoach_teams/`
- TASK-02: Add D8 live integration drift test for `scout/supercoach_teams/`
- TASK-03: Add D8 fixture + unit drift tests for `scout/supercoach_settings/`
- TASK-04: Add D8 live integration drift tests (classic + draft) for `scout/supercoach_settings/`
- TASK-05: Extend `scripts/scout-refresh.sh` + add cron lines for SC teams + settings
- TASK-06: One-time S3 seed + DB verification + roadmap/charter status flip + S3 profile docs refresh

---

## 2026-05-24: Scout Phase 3.5 — nrl.com match-centre DB extractors (harden + verify + populate)

**Goal:** Make the pre-existing S3→DB extractors for the nrl.com match-centre data trustworthy and run them — add fixture-based unit tests, fix the broken `--dry-run`, then populate the prod DB from the current S3 archives and verify. This lights up `matches`, `match_team_lists`, `player_match_stats`, `match_timeline`, `match_officials` — the wiki unlock that Phase 3 ingest fed.

**Context (verified 2026-05-24 — the extractors already exist, like Phase 3's ingest):** `scripts/data/populate_db_from_s3.py` orchestrates phases `identity → people → rounds → matches → team_lists → stats → timeline → standings → leaderboards → injuries`, idempotent UPSERTs, run via `python -m scripts.data.populate_db_from_s3 --phase all --seasons 2026`. The 4 match-centre phase modules (`phase_matches.py`, `phase_team_lists.py`, `phase_stats.py`, `phase_timeline.py`) all read `scout/nrlcom/match-centre/{comp}/{season}/round-{NN}/{slug}.json`, resolve identity via `teams.nrlcom_team_id` / `people.nrlcom_player_id` / `matches.external_match_id`, and UPSERT. All six target tables + identity columns exist (migrations through 069). **No new migrations.** **Missing:** zero tests; `--dry-run` is the META known-bug (each phase commits internally → the flag silently writes); no verified populate run.

**Scope:** the **4 match-centre-derived phases only** — `matches`, `team_lists`, `stats` (player_match_stats), `timeline` (+officials). `rounds`/`aux`(standings/leaderboards/injuries)/`identity`/`people`/`attributes` are out of test scope (other subsystems / Phase 4). NRL only (comp 111), season 2026 forward; historical backfill stays Phase 5.

**Constraints:**
- Unit tier = no IO, no env, no DB. Test the **pure** parse/map functions. `jeromelu_shared.config.Settings` has all-default fields, so importing a phase module needs no env — but the pure functions must not call S3/DB.
- `scripts.data.populate.*` is **not importable under pytest today** (pytest.ini `pythonpath = services/api packages/shared`; no `scripts/__init__.py` / `scripts/data/__init__.py`; `tests/unit/scripts/` is an empty `.gitkeep`). A prerequisite task fixes this.
- **Reuse the Phase 3 fixtures** — `tests/fixtures/scout/nrlcom_match_centre/canonical_response.json` (FullTime raiders-v-dolphins R12) + `canonical_response_upcoming.json`. They are real match-centre payloads; no new capture.
- The testability **refactor must be behavior-preserving** — mirror `phase_matches._extract_one` (the existing template): move the inlined row-building out of the DB loop into a pure `_extract_*` function that returns `list[dict]`; the loop then only UPSERTs.
- The `--dry-run` fix must thread a `commit` flag through ALL phases **including the per-50-archive checkpoint commits** in `phase_stats`/`phase_timeline`.
- The prod populate run is **operator-gated** — run on the box (it needs prod `DATABASE_URL` + S3 creds + the deployed code), like the Phase 3 seed. Idempotent UPSERTs make re-runs safe.

**Interface:**
- **Import path** (prereq): add repo root to `pytest.ini` (`pythonpath = . services/api packages/shared`) and add empty `scripts/__init__.py` + `scripts/data/__init__.py` so `from scripts.data.populate.phase_matches import _extract_one` resolves. `python -m scripts.data.populate_db_from_s3` still works (regular packages).
- **Pure extract functions** (the test seams):
  - `phase_matches._extract_one(payload, key, team_map, venue_map) -> dict | None` — **already exists** (template). Tests only.
  - `phase_stats._extract_stat_rows(payload, key, match_id, team_map, player_map) -> list[dict]` — **new** (extract from the inlined loop). Plus `_build_player_meta_map(payload)` (already pure) + `_FIELD_MAP`.
  - `phase_team_lists._extract_player_list_rows(payload, match_id, team_map, player_map) -> list[dict]` — **new** (players only; the coach path uses `_ensure_coach_person` DB I/O and stays in the loop, covered by the prod-run verify).
  - `phase_timeline._extract_timeline_rows(payload, key, match_id, team_map, player_map) -> list[dict]` + `_extract_official_rows(payload, key, match_id) -> list[dict]` — **new**.
- **`--dry-run` fix:** add `commit: bool = True` to `populate_matches`/`populate_team_lists`/`populate_player_match_stats`/`populate_timeline_and_officials` (and the other phases the orchestrator calls, for consistency); replace each `db.commit()` (final + checkpoint) with `if commit: db.commit()`; the orchestrator passes `commit=not args.dry_run` and keeps its final `db.rollback()` on dry-run. Then `--dry-run` computes counts and writes nothing.
- **Tests:** `tests/unit/scripts/data/populate/test_phase_{matches,stats,team_lists,timeline}.py`, mirroring the source tree under the unit tier; reuse the Phase 3 fixtures via the `fixtures_dir` conftest fixture.

**Verification strategy:**
- **Unit:** each `test_phase_*.py` feeds the FullTime fixture + fake id-maps to the pure `_extract_*` function and asserts the row dicts — e.g. matches: `status` mapping (`FullTime→final`), team resolution via map, `attendance==0→None`, referee extracted from officials; stats: `_FIELD_MAP` camelCase→snake (`tacklesMade→tackles_made`), jersey/position/is_on_field from player_meta, person_id/team_id resolution, is_home; team_lists: jersey/position/is_captain, person_id resolution, skip-when-no-person; timeline: `sequence` ordering, `event_type` default `"Unknown"`, running scores, officials fn/ln/role + skip-no-name. All run in CI (no IO).
- **`--dry-run`:** a unit/integration check that a dry-run leaves row counts unchanged (or, on the box, `--dry-run` followed by a count query showing no delta).
- **Prod populate (closure):** on the box, run the prerequisite + 4 phases for 2026 (`--phase all --seasons 2026`, or `identity,matches,team_lists,stats,timeline` in order), then verify row counts: `matches` (≥ the seeded R12 fixtures), `match_team_lists`, `player_match_stats`, `match_timeline`, `match_officials` all non-zero for season 2026; spot-check one match's player_match_stats count == its squad size.

**Documentation updates:**
- `scripts/data/populate/README.md` — create/update: the phase list, how to run, the pure-function test seams, the (now-fixed) `--dry-run`.
- `docs/build/META.md` — flip the "`populate_db_from_s3 --dry-run` is broken" known-bug entry to fixed (after the fix task).
- `docs/operations/data-catalogue/` (per the data-docs trinity) — note that `matches`/`match_team_lists`/`player_match_stats`/`match_timeline`/`match_officials` are populated by the `phase_*` extractors from `scout/nrlcom/match-centre/*`.
- `docs/build/runs/2026-05-24-scout-phase-3.5-nrlcom-extractors.md` — run report (created when the first task lands; finalised at closure).

**Tasks:** TASK-13 → TASK-19 (in TASKS.md).

---

## Completed work

Completed plans are **not** archived in this file. When a plan's tasks are all done, its durable record is a run report under [`docs/build/runs/`](./runs/) (see the [index](./runs/README.md)) and the plan is removed from "Active plan" above. This document holds only active/future plans; the run reports are the system of record for what shipped.
