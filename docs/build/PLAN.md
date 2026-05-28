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

## 2026-05-28: Scout Phase 4.5 — nrl.com stats + players roster (D8 harden, schedule, seed)

**TL;DR — this is a Phase 4-style hardening replay, not greenfield.** Discovery (2026-05-28) found both `services/api/app/scout/nrlcom_stats/` and `services/api/app/scout/nrlcom_players_roster/` already exist with fetchers, routes, READMEs, and `make` targets; migration `060_stat_leaderboards.sql` is applied; `scripts/data/populate/phase_aux.py:populate_stat_leaderboards` is shipped and wired into `populate_db_from_s3.py` (phase 8, `--phase leaderboards`); the lineage + catalogue docs already exist and claim `~4,594 rows shipped (2013-2025)`. What's missing is the **D8 drift contract** (strict envelope + nested item/leader models, fixture, unit tests, route ValidationError-aborts, env-flagged live drift test), **extractor unit tests** via pure-function refactor (the Phase 4 TASK-25 precedent), **cron scheduling** for both pipelines, and the **prod seed + DB verification** that closes the loop.

NRL only (comp 111), current season 2026, forward-only — historical backfill stays Phase 5. SC Draft mode (charter D6 "optional") and folding `jeromelu_shared/players/nrlcom_refresh.py` (HTML profile scraper) into a D9-compliant folder both stay deferred — explicit scope decision (2026-05-28).

**Goal:** Ship Phase 4.5 to the same operational bar as Phase 4 — both nrl.com ingest pipelines are D8-hardened (envelope + all extractor-read nested items strictly modelled), scheduled, drift-protected end-to-end, and have a verified prod seed with DB row counts proving the extractor pipeline lights up.

**Constraints:**
- D8 model strictness extends as deep as the extractor reads. For `nrlcom_stats`, `populate_stat_leaderboards` reads four nested levels (`<scope>Stats[].title`, `groups[].title/statId`, `leaders[].firstName/lastName/teamNickName/teamName/playerId/value`) — so envelope **and** category **and** subgroup **and** leader are all `extra="forbid"`. For `nrlcom_players_roster`, since this phase ships **no** new DB extractor (S3-only — the existing `nrlcom_refresh.py` HTML-scrape enrichment stays untouched per scope), strict modelling protects the envelope + the load-bearing `profileGroups[].profiles[].profile`-level identity fields, with deeper opaque-typed slots until an extractor lands.
- Idempotency on S3 paths is unchanged: `scout/nrlcom/stats/{comp}/{season}.json` (one key per season — overwrites) and `scout/nrlcom/players-roster/{comp}/team-{team_id}.json` (one key per team — overwrites).
- Per-pipeline rate-limit: `nrlcom_players_roster` refresh-all walks 17 teams sequentially with **≥1 second** between fetches (architectural risk #2).
- Cron slots must not collide with the 18:00-18:45 UTC daily NRL.com block (draw/match-centre/casualty/ladder) or the Mon 23:00-23:35 UTC weekly block (channel-stats/videos/SC teams/SC settings); position before the 00:30 UTC `cron-report` digest so the trailing-24h email covers them.
- No `git add -A` / no batching; commit + push per task per `META.md`.

**Interface:**

*nrlcom-stats (TASK-29 → TASK-30, TASK-34):*
- New file: `services/api/app/scout/nrlcom_stats/models.py` — four strict `BaseModel`s (`extra="forbid"`):
  - `NrlcomStats` (envelope): `playerStats: list[StatCategory]`, `teamStats: list[StatCategory]`, plus the remaining top-level keys observed live (capture during fixture run; the implementer records the actual envelope shape from `https://www.nrl.com/stats/data?competition=111&season=2026`).
  - `StatCategory` (one item of `<scope>Stats[]`): `title: str`, `groups: list[StatSubgroup]`, plus any other category-level keys observed live.
  - `StatSubgroup` (one item of `groups[]`): `title: str`, `statId: int | None`, `leaders: list[StatLeader]`, plus any other subgroup-level keys observed live.
  - `StatLeader` (one item of `leaders[]`): `firstName: str | None`, `lastName: str | None`, `teamNickName: str | None`, `teamName: str | None`, `playerId: int | None`, `value: float | int | str | None`, plus any other leader-level keys observed live. **Every field required-present-but-nullable** (the `NrlcomDraw.disclaimer` convention — key must exist so a rename/removal trips drift; null value tolerated). `extra="forbid"` on all four catches a new key.
- New file: `tests/fixtures/scout/nrlcom_stats/canonical_response.json` — captured live (≥1 of each scope/category/subgroup/leader present).
- New folder: `tests/unit/api/scout/nrlcom_stats/` with `__init__.py` + `test_models.py` — 4 tests: canonical parses; unknown top-level field raises naming it; unknown leader field raises; missing required nested key raises.
- New folder: `tests/integration/scout/nrlcom_stats/` with `__init__.py` + `test_response_shape.py` — env-flagged (`SCOUT_DRIFT_LIVE=1`) live drift test mirroring `nrlcom_casualty_ward/test_response_shape.py` exactly.
- Modified: `services/api/app/scout/nrlcom_stats/routes.py` — import `pydantic.ValidationError` + the new `NrlcomStats` model; after `archive_response(...)` (S3 first), add `NrlcomStats.model_validate(data)` + `detail["validated"] = True`; insert a new `except ValidationError → run.fail + HTTPException(500)` arm **before** the generic `except Exception` (mirror the `nrlcom_ladder/routes.py` arm order line-for-line). `NrlcomStatsFetchError → 502` arm unchanged.
- Modified: `scripts/data/populate/phase_aux.py` — extract two pure functions for unit testability (mirrors TASK-25's pattern for ladder + casualty):
  - `_extract_leader_rows(payload: dict, *, key: str, competition: int, season: int, team_map: dict[str, str], player_map: dict[int, str]) -> list[dict[str, Any]]` — pure projection of one `/stats/data` archive into `stat_leaderboards`-shaped row dicts. No DB. Reads both `playerStats` + `teamStats` blocks.
  - The inline body of `populate_stat_leaderboards` switches from the current nested-for loop to calling `_extract_leader_rows` per archive and `db.execute(upsert_sql, row)` per returned row. UPSERT SQL + counters + `commit` guard unchanged (byte-equivalent post-refactor).
- New file: `tests/unit/scripts/data/populate/test_phase_leaderboards.py` — 5+ tests over `_extract_leader_rows` using a trimmed copy of the TASK-29 canonical fixture: (a) one-leader projection — exact field map; (b) `scope='player'` resolves `person_id` via `player_map` when `playerId` present, `None` otherwise; (c) `scope='team'` always emits `person_id=None`; (d) `leader_value` parses float; coerces `None` on `""`/non-numeric; (e) team nickname resolves via `team_map` lower-case lookup, falls back to `None` when unknown.

*nrlcom-players-roster (TASK-31 → TASK-32 → TASK-33):*
- New file: `services/api/app/scout/nrlcom_players_roster/models.py` — strict `BaseModel`s:
  - `NrlcomPlayersRoster` (envelope, `extra="forbid"`): `profileGroups: list[ProfileGroup]`, plus all other observed top-level keys.
  - `ProfileGroup` (one of `profileGroups[]`, `extra="forbid"`): `profiles: list[Profile]`, plus the observed group-level keys (likely a `title`/`type` discriminator — implementer confirms live).
  - `Profile` (one of `profiles[]`, `extra="forbid"`): the load-bearing identity fields per a captured response. As a first cut: `profile: ProfileBody | None`, plus the visible top-level wrapping keys. If the upstream nests biographical fields one level deeper, the implementer adds `ProfileBody` (also `extra="forbid"`) with `firstName: str | None`, `lastName: str | None`, `playerId: int | None`, `positions: list[Any] | None`, `theme: dict[str, Any] | None`, plus the rest observed-required-but-nullable per the convention.
  - **Boundary note:** because Phase 4.5 ships no DB extractor against `/players/data`, strict modelling stops at the identity/wrapper level — opaque slots (`theme`, `positions`, large biographical blocks) stay `dict[str, Any] | None` until an extractor lands. Envelope guard + group/profile guard still trip on rename/addition.
- New file: `tests/fixtures/scout/nrlcom_players_roster/canonical_response.json` — captured live for ONE team (`team_id=500011` Storm, comp=111). Single team is sufficient — the route is per-team.
- New folder: `tests/unit/api/scout/nrlcom_players_roster/{__init__.py,test_models.py}` — 4 tests: canonical parses; unknown top-level raises naming it; unknown profile-level raises; missing required profile identity field raises.
- New folder: `tests/integration/scout/nrlcom_players_roster/{__init__.py,test_response_shape.py}` — env-flagged live test against `team_id=500011`.
- Modified: `services/api/app/scout/nrlcom_players_roster/routes.py` — D8 strict-parse + `validated:true` + 500-on-drift arm, exact mirror of `nrlcom_ladder/routes.py`.
- New constant: `services/api/app/scout/nrlcom_players_roster/teams.py` exposing `NRL_TEAM_IDS: list[tuple[str, int]]` — the 17 NRL.com internal `team_id` values + a friendly short-name per team (derived by the implementer from a recent `scout/nrlcom/ladder/111/2026/round-NN.json` or `scout/nrlcom/draw/111/2026/round-NN.json` already in S3 — these objects expose `homeTeam.teamId` / `awayTeam.teamId` per fixture and `theme`/`nickname` per ladder position).
- New endpoint: `POST /api/admin/scout/nrlcom-players-roster/refresh-all?competition=N` — walks `NRL_TEAM_IDS`, calls the existing `run_nrlcom_players_roster(...)` once per team with `time.sleep(1.0)` between calls (per-origin polite rate), returns `{"run_id_envelope": str, "ok": true, "competition": N, "teams_walked": 17, "results": [{"team_id": int, "ok": bool, "profiles": int, "s3_archive_key": str, "validated": bool}], "errors": [{"team_id": int, "error": str}]}`. The envelope itself opens a `start_deterministic_run(pipeline="nrlcom-players-roster-refresh-all", ...)` audit row with `detail_json` summarising the 17 sub-runs; per-team runs continue to land as their own `agent_runs` rows. **Non-aborting per-team**: a single-team failure is captured under `errors[]` and the envelope continues — match-centre's "fail one match, keep walking" precedent.

*Cron (TASK-35):*
- Modified: `scripts/scout-refresh.sh` — new cases:
  - `nrlcom-stats) ENDPOINT="nrlcom-stats?competition=111&season=$(date -u +%Y)" ;;`
  - `nrlcom-players-roster) ENDPOINT="nrlcom-players-roster/refresh-all?competition=111" ;;`
  - Sync the `# Usage:` header line and the `*)` catch-all error string identically.
- Modified: `scripts/cron.d/jeromelu` — two new daily lines positioned in the existing 18:xx UTC nrl.com block, before `30 16 * * * pg-backup` and well before `30 0 * * * cron-report`:
  - `50 18 * * * ubuntu /opt/jeromelu/scripts/scout-refresh.sh nrlcom-stats` (04:50 AEST)
  - **Players-roster runs WEEKLY**, Tuesday after the weekly SC block: `40 23 * * 1 ubuntu /opt/jeromelu/scripts/scout-refresh.sh nrlcom-players-roster` (Tuesday 09:40 AEST) — slots after the Mon 23:30/23:35 SC-teams/settings lines. Player biographical data changes slowly; weekly is right.

*Seed + DB verification (TASK-36, run on prod box):*
- Endpoints (live, expected `validated:true`):
  - `POST /api/admin/scout/nrlcom-stats?competition=111&season=2026` → `{ok:true, player_stat_groups:>0, team_stat_groups:>0, validated:true, s3_archive_key:"scout/nrlcom/stats/111/2026.json"}`
  - `POST /api/admin/scout/nrlcom-players-roster/refresh-all?competition=111` → 17 teams walked, `validated:true` per team, `errors:[]` (or all errors documented in the run report).
- Container-side populate (Phase 3.5 `docker cp scripts → /runtmp` procedure):
  - `docker exec jeromelu-api python -m scripts.data.populate_db_from_s3 --phase leaderboards --competition 111` → `stat_leaderboards` rows refreshed.
- Post-seed DB checks (read-only via `docker exec jeromelu-postgres psql`):
  - `SELECT COUNT(*) FROM stat_leaderboards WHERE season=2026 AND competition=111;` → matches the upstream cardinality (e.g. ~25 leaders × number of subgroups).
  - `SELECT COUNT(*) FILTER (WHERE person_id IS NOT NULL) * 100.0 / COUNT(*) FROM stat_leaderboards WHERE scope='player' AND season=2026 AND competition=111;` → expected ≥80% person_id resolution (the Phase 4 ladder bar).
  - Spot-check the top leader for at least one well-known subgroup (e.g. Total Points) against the live `https://www.nrl.com/stats/...` web view — should match.
- S3 checks:
  - `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/stats/111/` → `2026.json` present, ~275KB, recent stamp.
  - `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/players-roster/111/` → all 17 `team-{team_id}.json` keys present, recent stamp.

**Verification strategy:**

- *End-to-end:* `POST /api/admin/scout/nrlcom-stats?...` returns `validated:true` and writes a `scout/nrlcom/stats/...` S3 object identical in shape to the captured fixture; `POST /api/admin/scout/nrlcom-players-roster/refresh-all?...` returns 17 per-team `validated:true` results and writes 17 S3 objects; running `populate_db_from_s3 --phase leaderboards` against those archives writes ≥1 `stat_leaderboards` row per subgroup with team/person resolution rates meeting the bar above.
- *Unit:* `pytest tests/unit/api/scout/nrlcom_stats/ tests/unit/api/scout/nrlcom_players_roster/ tests/unit/scripts/data/populate/test_phase_leaderboards.py` → all green; full scout unit suite shows no regression (baseline 102 passed per Phase 4 closure → ≥102 + new tests).
- *Integration (env-flagged):* `SCOUT_DRIFT_LIVE=1 pytest tests/integration/scout/nrlcom_stats/test_response_shape.py tests/integration/scout/nrlcom_players_roster/test_response_shape.py` → 2 passed against live nrl.com. Skip-mode (`SCOUT_DRIFT_LIVE` unset) → 2 skipped with the exact reason text matching the casualty-ward precedent.
- *Deliberate-break proof (per TASK-30 + TASK-32):* introducing a required field that doesn't exist live (e.g. `tries_per_game: int` on `StatLeader`) → live drift test fails naming the new field; revert; `git diff HEAD` empty.
- *Cron first-fire (operator/time-gated):* once the box pulls past the cron commit, `/var/log/jeromelu/scout-refresh.log` shows the next-scheduled `nrlcom-stats` and `nrlcom-players-roster` lines clean (`status=200`). Mirrors the Phase 3 TASK-12 / Phase 4 TASK-26 deferral pattern; the TASK-36 seed already proves the endpoints end-to-end.

**Documentation updates** (treat as production code per project CLAUDE.md):

- `docs/agents/crew/scout/roadmap.md` — flip the Phase 4.5 section from "Backlog" to "Shipped (2026-05-28)" listing what landed. Move the SC Draft + `nrlcom_refresh.py`-fold items into a "Deferred" sub-bullet (explicitly scoped out 2026-05-28).
- `docs/agents/crew/scout/charter.md` — flip the Status cells for `nrlcom_stats` and `nrlcom_players_roster` in the "Data — nrl.com" table from "🟡 not built — Phase 4.5" / "🟡 partially exists" to "✅ shipped (Phase 4.5)". Tighten D7 idempotency table to add the natural keys for `stat_leaderboards` and `players_roster`. D13 inventory: confirm `extract_stat_leaderboards` row reflects the shipped function (it already does); no change needed for `nrlcom_players_roster` (no DB extractor this phase).
- `services/api/app/scout/nrlcom_stats/README.md` — flip "DB extraction: Deferred" to live (`populate_stat_leaderboards` already exists; document it); add `## Tests` section pointing at the unit + live drift tests; add cron cadence (Daily 18:50 UTC).
- `services/api/app/scout/nrlcom_players_roster/README.md` — same flips; add the `refresh-all` endpoint usage; document `NRL_TEAM_IDS` (where the 17 ids live + how to add new teams); document the explicit scope decision that no JSON-side DB extractor ships this phase (the existing HTML-scrape `nrlcom_refresh.py` enrichment path is unchanged and lives in `jeromelu_shared`); document cron (Weekly Tue 23:40 UTC).
- `scripts/data/populate/README.md` — note `_extract_leader_rows` is now the pure projection seam for `stat_leaderboards`; mirror the Phase 4 TASK-25 entry for `phase_aux.py`.
- `docs/operations/data-lineage/stat_leaderboards.md` — refresh post-seed counts (2026 rows / team / person resolution %).
- `docs/operations/data-catalogue/stat_leaderboards.md` — no field changes (table unchanged); skim to confirm.
- `docs/build/META.md` — no new invariants expected; only update if the seed surfaces a class of bug we'd want to warn about (e.g. another `jsonb_build_object` latent fixed during seed).
- New run report at `docs/build/runs/2026-05-28-scout-phase-4-5-stats-players-roster.md` created when the first task is checked off; row added to `docs/build/runs/README.md` (newest first); set status to Shipped after TASK-36 closes.

**Tasks:**
- TASK-29: nrlcom-stats — D8 strict models (envelope + 3 nested) + fixture + unit drift tests
- TASK-30: nrlcom-stats — wire strict-parse into route + env-flagged live drift test
- TASK-31: nrlcom-players-roster — D8 strict models + fixture + unit drift tests
- TASK-32: nrlcom-players-roster — wire strict-parse into route + env-flagged live drift test
- TASK-33: nrlcom-players-roster — `refresh-all` endpoint walking 17 NRL teams server-side with 1 req/sec spacing
- TASK-34: extractor unit tests for `populate_stat_leaderboards` via pure-function refactor (`_extract_leader_rows`)
- TASK-35: schedule cron for nrlcom-stats (daily 18:50 UTC) + nrlcom-players-roster (weekly Tue 23:40 UTC)
- TASK-36: prod seed + DB verification + docs (Phase 4.5 closure)




## Completed work

Completed plans are **not** archived in this file. When a plan's tasks are all done, its durable record is a run report under [`docs/build/runs/`](./runs/) (see the [index](./runs/README.md)) and the plan is removed from "Active plan" above. This document holds only active/future plans; the run reports are the system of record for what shipped.
