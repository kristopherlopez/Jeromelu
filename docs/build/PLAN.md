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

## 2026-05-24: Scout Phase 3 — nrl.com draw + match-centre ingest hardening

**Goal:** Take the already-built `scout/nrlcom_draw/` and `scout/nrlcom_match_centre/` capture pipelines from "fetch + S3 archive, but no strict-parse, no tests, no schedule" to **charter-compliant, drift-tested, scheduled, seeded** — the same D8 / cron / seed discipline applied in Phases 1/2/2.5. **Ingest only**; the DB extractors (`matches`, `match_team_lists`, `player_match_stats`, `match_timeline`, `match_officials`) are deferred to Phase 3.5.

**Context (verified 2026-05-24):** Both pipelines already have `fetcher.py` + `routes.py` (mounted at `/api/admin/scout/nrlcom-draw` and `/nrlcom-match-centre`) + Makefile targets + S3 archive + agent_audit. **Missing:** `models.py` (no D8 strict model), strict-parse wired into the routes (they archive raw and never validate — drift passes silently), fixtures + unit + live drift tests, and cron scheduling.

**Constraints:**
- Charter D8: each pipeline ships `tests/fixtures/scout/<pipeline>/canonical_response.json`, strict Pydantic models (`extra='forbid'`), a fixture-mode unit test, and an env-flagged (`SCOUT_DRIFT_LIVE=1`) live-mode integration test. The route must **wire the strict parse in** so drift surfaces in prod, not just in CI.
- Match-centre payload is ~100KB / 29 top-level keys, deeply nested → **envelope-guard model only** (top-level keys as opaque, like `supercoach_settings`). Draw is small → model the envelope **and** each fixture (the pipeline depends on `fixtures[].matchCentreUrl`).
- NRL men's only (competition 111). NRLW / state cups are a later config follow-on.
- Forward-only, daily-during-the-round cron. Historical backfill stays Phase 5 (D12).
- Scout scrapers don't auto-adapt to drift (D8 / META) — tests fail loudly; the human decides the fix.
- META: cron lives in `scripts/cron.d/jeromelu` + `scripts/scout-refresh.sh`, deployed via `lightsail-deploy.sh`; never hand-edit the prod crontab. On-box admin calls need `--resolve` (hairpin-NAT). Session-scoped staging.

**Interface (top-level keys verified against live capture 2026-05-24, comp 111 / season 2026 / round 12 — the implementer re-captures the fixture and enumerates the exact key set + types):**
- New `services/api/app/scout/nrlcom_draw/models.py`:
  - `NrlcomDraw(BaseModel)` — `model_config = ConfigDict(extra="forbid")`. Top-level keys observed: `fixtures: list[DrawFixture]`, `byes: list[dict[str, Any]]`, `calendarUrl: str`, `disclaimer: str | None`, `downloadUrl: str`, `filterCompetitions/filterRounds/filterSeasons/filterTeams: list[dict[str, Any]]`, `selectedCompetitionId/selectedRoundId/selectedSeasonId: int`, `showOdds: bool`, `showTeamPositions: bool`.
  - `DrawFixture(BaseModel)` — `extra="forbid"`. Keys observed: `matchCentreUrl: str` (**load-bearing**), `homeTeam/awayTeam: dict[str, Any]`, `clock: dict[str, Any]`, `callToAction/secondaryCallToAction: dict[str, Any] | None`, `isCurrentRound: bool`, `matchMode: str`, `matchState: str`, `roundTitle: str`, `type: str`, `venue: str`, `venueCity: str`.
- New `services/api/app/scout/nrlcom_match_centre/models.py`:
  - `NrlcomMatchCentre(BaseModel)` — `extra="forbid"`, **envelope only**. The 29 top-level keys as opaque/typed: `matchId` (str|int), `homeTeam/awayTeam/competition/officials/stats/weather/groundConditions/venue?: dict[str, Any]`, `positionGroups/timeline: list[Any]`, int scalars (`attendance`, `gameSeconds`, `roundNumber`, `segmentCount`, `segmentDuration`), str scalars (`matchMode/matchState/roundTitle/startTime/updated/url/venue/venueCity/imageUrl`), bool scalars (`animateMatchClock/hasExtraTime/hasOnFieldTracking/showPlayerPositions/showTeamPositions`). Enumerate exactly from the fixture (some may be nullable).
- Route changes:
  - `nrlcom_draw/routes.py` — after `archive_response(...)`, `NrlcomDraw.model_validate(data)`; on `ValidationError` record failed audit + `raise HTTPException(500, ...)` so drift surfaces. Add `"validated": True` to detail on success. (Archive **before** validate so the raw is captured for drift forensics even when validation fails.)
  - `nrlcom_match_centre/routes.py` — make `round` optional (`round: int | None = Query(default=None)`); when `None`, resolve current via the draw's `selectedRoundId`. After archiving each match, `NrlcomMatchCentre.model_validate(match_data)`; collect `validation_failures: list[{slug, error}]` (do **not** abort the walk); surface the count in detail + summary so the cron-health email flags drift.
- Cron:
  - `scripts/scout-refresh.sh` — two new cases mapping to query-string ENDPOINTs: `nrlcom-draw) ENDPOINT="nrlcom-draw?competition=111&season=$(date -u +%Y)"` and `nrlcom-match-centre) ENDPOINT="nrlcom-match-centre?competition=111&season=$(date -u +%Y)"` (round omitted → current, resolved server-side); update usage string.
  - `scripts/cron.d/jeromelu` — two daily lines, proposed `0 18 * * *` (draw) and `15 18 * * *` (match-centre) = 04:00 / 04:15 AEST, capturing the prior day's completed games off-peak; tunable.
- S3 keys (already produced by the routes, unchanged): `scout/nrlcom/draw/{comp}/{season}/round-{NN}.json`, `scout/nrlcom/match-centre/{comp}/{season}/round-{NN}/{slug}.json`.
- New env vars: none.

**Verification strategy:**
- End-to-end: `make scout-nrlcom-draw COMPETITION=111 SEASON=2026` and `make scout-nrlcom-match-centre COMPETITION=111 SEASON=2026` against prod return `ok:true` with `s3_archive_key`(s); `aws s3 ls scout/nrlcom/draw/111/2026/` and `.../match-centre/111/2026/round-NN/` show today-dated keys.
- Tests: unit drift tests (fixtures parse; unknown/missing fields raise) always-on in CI; live drift tests env-flagged (`SCOUT_DRIFT_LIVE=1`) hit real nrl.com; deliberate model-break makes them fail naming the field.
- Route wiring: deliberately pollute the model → the draw endpoint 500s; the match-centre endpoint reports `validation_failures`.
- Cron: `bash -n`, dry-run case match (URL carries `?competition=111&season=YYYY`), 5-field cron lines + `lightsail-deploy.sh` sync grep.

**Documentation updates:**
- `services/api/app/scout/nrlcom_draw/README.md` + `nrlcom_match_centre/README.md` — add `## Tests` sections; update cadence to "daily cron (current round)".
- `docs/agents/crew/scout/roadmap.md` — Phase 3 ingest → ✅ Shipped (explicitly note extractors deferred to Phase 3.5).
- `docs/agents/crew/scout/charter.md` — flip the nrl.com draw + match-centre Status cells (if present in the nrl.com data table).
- `docs/operations/data-sources/...` — generate S3 profile docs for `scout/nrlcom/draw/` and `scout/nrlcom/match-centre/` via `scripts/profile_s3_json.py`.
- `docs/build/runs/2026-05-24-scout-phase-3-nrlcom-ingest.md` — run report (created when the first task lands; finalised at closure).

**Tasks:** TASK-07 → TASK-12 (in TASKS.md).

---

## Completed work

Completed plans are **not** archived in this file. When a plan's tasks are all done, its durable record is a run report under [`docs/build/runs/`](./runs/) (see the [index](./runs/README.md)) and the plan is removed from "Active plan" above. This document holds only active/future plans; the run reports are the system of record for what shipped.
