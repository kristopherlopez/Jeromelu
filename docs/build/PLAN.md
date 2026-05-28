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

## 2026-05-28: Scout Phase 4 — nrl.com casualty ward + ladder (harden, schedule, seed) + retire worker-scraper

**Goal:** Bring the casualty-ward and ladder pipelines up to the same "shipped" bar as Phase 3 (D8-hardened ingest, scheduled, seeded, extractors tested), then retire the orphaned `services/worker-scraper/` Temporal worker — closing the charter's Phase 4.

**Context — this is a hardening replay, not greenfield.** Discovery (2026-05-28) found Phase 4 substantially pre-built:
- ✅ Ingest folders `services/api/app/scout/nrlcom_casualty_ward/` and `nrlcom_ladder/` exist with `fetcher.py` + `routes.py` + `README.md` + `__init__.py`, wired into `scout/routes.py`.
- ✅ Make targets `scout-nrlcom-casualty-ward` and `scout-nrlcom-ladder` exist in the Makefile.
- ✅ DB extractors exist: `populate_injuries` (casualty → `injuries`, a state machine over daily snapshots) and `populate_team_standings` (ladder → `team_standings`) in `scripts/data/populate/phase_aux.py`, wired into `scripts/data/populate_db_from_s3.py` as phases `injuries` and `standings`.
- ✅ Migrations exist: `031_injuries.sql` (now points at `people.person_id` — `player_entity_id` was added→dropped via `036`/`038`, team FK re-pointed in `041`) and `059_team_standings.sql` (one row per `(nrlcom_team_nickname, competition, season, round)`, 22 metrics + `raw_payload` + `s3_archive_key`).
- ✅ Backfill driver `scripts/data/scout_backfill.py` already supports both pipelines.

**The gaps Phase 4 closes** (each mirrors what Phase 3 / 3.5 did for draw + match-centre):
1. **No D8 drift contract** on either pipeline — no `models.py`, routes don't strict-parse, no fixtures, no unit/live drift tests. (Draw + match-centre have all of these.)
2. **No tests for the two extractors** — Phase 3.5 only covered `phase_matches`/`stats`/`team_lists`/`timeline`; `phase_aux` (injuries + standings) is untested except for the `--dry-run` signature test.
3. **Not scheduled** — `scripts/scout-refresh.sh` + `scripts/cron.d/jeromelu` carry draw + match-centre only.
4. **Not seeded** to prod (no S3 archive + no DB extraction verified live).
5. **`worker-scraper/` still in tree** — already orphaned (no code, compose, CI, or deploy-script reference; ~9 docs mention it). D4 + the roadmap say retire it at the end of Phase 4.

**Decisions locked (interview 2026-05-28):**
- **D8 depth: strict envelope + item/stats.** Unlike draw/match-centre (deferred extractors → envelope-only, nested objects opaque), the casualty/ladder extractors are LIVE and read nested fields by exact key (`casualty["expectedReturn"]`, ladder `stats["points for"]`). So model the envelope **and** the casualty item (8 fields) **and** the ladder position + its 22-metric `stats` object strictly (`extra="forbid"`), so a renamed/removed nested key fails loudly instead of silently nulling a DB column. Raw is archived to S3 *before* validation (existing pattern), so a 500-on-drift never loses the capture.
- **Extractor freshness: manual/backfill (Phase 3.5 precedent).** Schedule *ingest* only; run the extractor once at seed time to prove the path; leave it operator-run. Scheduled extraction + baking `scripts/` into the api image is a cross-cutting infra follow-up (affects all nrlcom pipelines, already flagged in the Phase 3.5 report) — **out of scope, surfaced as a follow-up, not self-queued.**
- **worker-scraper: delete the directory + sweep docs.** Git-reversible; fulfils D4.

**Constraints:**
- **NRL only (competition 111), season 2026, forward-only.** Historical backfill (ladder reaches ~30 seasons; casualty is current-season-only) is **Phase 5 (D12)** — not this plan.
- Abort semantics: casualty + ladder are **single-envelope** fetches (one object, not a per-match walk), so drift → `HTTPException(500)` + failed audit (the **draw** precedent), NOT the non-aborting per-match `validation_failures` collection used by match-centre.
- Respect session-scoped commits (`git diff --cached --stat` before each commit; the working tree already has unrelated dirty files from other sessions — never `git add -A`).
- Apply no new migrations (031 + 059 already cover both tables); do not hand-apply SQL.

**Interface:**

*New models (per D9 folder-per-pipeline):*
- `services/api/app/scout/nrlcom_casualty_ward/models.py`
  - `Casualty(BaseModel)` — `model_config = ConfigDict(extra="forbid")`. Required `str`: `firstName`, `lastName`, `teamNickname` (extractor-load-bearing). Nullable-but-present: `injury: str | None`, `expectedReturn: str | None`, `imageUrl: str | None`, `url: str | None`, `theme: <type from fixture> | None`. Implementer enumerates the exact key set + `theme` type from the captured live fixture.
  - `NrlcomCasualtyWard(BaseModel)` — `extra="forbid"`; `casualties: list[Casualty]` + the filter/metadata top-level keys enumerated from the fixture (e.g. `filterCompetitions`, `filterSeasons`, …), typed `list[dict[str, Any]]` / scalars as the fixture shows.
- `services/api/app/scout/nrlcom_ladder/models.py`
  - `LadderStats(BaseModel)` — `model_config = ConfigDict(extra="forbid", populate_by_name=True)`. The 22 metrics, **space-separated upstream keys mapped via `Field(alias=...)`** because Python identifiers can't contain spaces. Baseline (implementer confirms/adjusts against the live fixture):
    ```python
    played: int | None = None
    wins: int | None = None
    lost: int | None = None
    drawn: int | None = None
    byes: int | None = None
    points: int | None = None
    points_for: int | None = Field(default=None, alias="points for")
    points_against: int | None = Field(default=None, alias="points against")
    points_difference: int | None = Field(default=None, alias="points difference")
    bonus_points: int | None = Field(default=None, alias="bonus points")
    form: str | None = None
    streak: str | None = None
    home_record: str | None = Field(default=None, alias="home record")
    away_record: str | None = Field(default=None, alias="away record")
    day_record: str | None = Field(default=None, alias="day record")
    night_record: str | None = Field(default=None, alias="night record")
    average_winning_margin: float | None = Field(default=None, alias="average winning margin")
    average_losing_margin: float | None = Field(default=None, alias="average losing margin")
    close_games: int | None = Field(default=None, alias="close games")
    golden_point: int | None = Field(default=None, alias="golden point")
    players_used: int | None = Field(default=None, alias="players used")
    odds: str | None = None
    ```
  - `LadderPosition(BaseModel)` — `extra="forbid"`; required/load-bearing `teamNickname: str`, `stats: LadderStats`; `position: int | None`, `movement: str | None`, plus the other position-level keys enumerated from the fixture (`teamName`, `theme`, etc.) typed as the fixture shows.
  - `NrlcomLadder(BaseModel)` — `extra="forbid"`; `positions: list[LadderPosition]` + filter metadata top-level keys from the fixture.

*Routes touched (strict-parse wiring — single-envelope / abort-on-drift):*
- `services/api/app/scout/nrlcom_casualty_ward/routes.py` — after `archive_response(...)`, call `NrlcomCasualtyWard.model_validate(data)`; set `detail["validated"] = True`; add `except ValidationError as e: run.fail(...); raise HTTPException(500, ...)` ordered **before** the generic `except Exception`. (The `NrlcomCasualtyFetchError → 502` arm is unchanged.)
- `services/api/app/scout/nrlcom_ladder/routes.py` — same wiring with `NrlcomLadder`.

*Extractor refactor (for testability — behaviour-preserving, mirrors Phase 3.5):*
- `scripts/data/populate/phase_aux.py`
  - Extract a pure `_extract_standing_rows(payload: dict, *, key: str, competition: int, season: int, round_no: int, team_map: dict[str,str]) -> list[dict]` from `populate_team_standings`; the caller UPSERTs the returned rows via the unchanged `upsert_sql`. Counters/commit logic unchanged.
  - Extract a pure `_casualty_to_row(c: dict, *, team_map, people_lookup) -> dict | None` from the inner loop of `populate_injuries` (maps a casualty entry → the field dict it INSERTs: resolved `team_id`/`person_id`, `description`, `body_part=injury`, `expected_return_round`, `expected_return_text`, `url`, `team_nickname`; returns `None` for skip-no-name/no-team). The chronological state-machine (open/close rows against the DB) stays inline. `_bucket_status` is already pure.

*New tests:*
- `tests/unit/api/scout/nrlcom_casualty_ward/{__init__.py,test_models.py}` — canonical parse + 3 negatives (unknown top-level, unknown casualty field, missing `expectedReturn` *value* via null when required / missing-required-`teamNickname`).
- `tests/unit/api/scout/nrlcom_ladder/{__init__.py,test_models.py}` — canonical parse + 3 negatives (unknown top-level, unknown `stats` key — proves a new metric trips drift, missing-required-`teamNickname`).
- `tests/integration/scout/nrlcom_casualty_ward/{__init__.py,test_response_shape.py}` — env-flagged (`SCOUT_DRIFT_LIVE=1`) live drift test against `/casualty-ward/data?competition=111`.
- `tests/integration/scout/nrlcom_ladder/{__init__.py,test_response_shape.py}` — env-flagged live drift against `/ladder/data?competition=111&season=<current>`.
- `tests/unit/scripts/data/populate/test_phase_aux.py` — fixture-based unit tests for `_extract_standing_rows` (22-metric incl. space-key→column mapping, team resolution, `position` fallback to enumerate index) + `_casualty_to_row` + `_bucket_status` (Round-N gap bucketing, indefinite/season/training/test).

*New fixtures:*
- `tests/fixtures/scout/nrlcom_casualty_ward/canonical_response.json` (full live response — ~98 entries, small).
- `tests/fixtures/scout/nrlcom_ladder/canonical_response.json` (full live response — 17 teams, small).

*Cron / scheduling:*
- `scripts/scout-refresh.sh` — add `nrlcom-casualty-ward` (`ENDPOINT="nrlcom-casualty-ward?competition=111"`) and `nrlcom-ladder` (`ENDPOINT="nrlcom-ladder?competition=111&season=$(date -u +%Y)"`) cases; sync the usage string + file-header.
- `scripts/cron.d/jeromelu` — two daily lines, off-peak, no collision with the existing 18:00/18:15 nrlcom slots: casualty `30 18 * * * ubuntu /opt/jeromelu/scripts/scout-refresh.sh nrlcom-casualty-ward`; ladder `45 18 * * * ubuntu /opt/jeromelu/scripts/scout-refresh.sh nrlcom-ladder`.

*Files deleted (worker-scraper retirement):*
- `services/worker-scraper/` (entire directory).

**Verification strategy:**
- **End-to-end (seed, TASK-27):** on the prod box (loopback `--resolve` per the META "on-box admin API" note; `ADMIN_KEY` from `/opt/jeromelu/.env`):
  - `POST /api/admin/scout/nrlcom-casualty-ward?competition=111` → `{ok:true, casualties:>0, validated:true, s3_archive_key:"scout/nrlcom/casualty-ward/111/<YYYYMMDD>.json"}`.
  - `POST /api/admin/scout/nrlcom-ladder?competition=111&season=2026` → `{ok:true, teams:>0, validated:true, s3_archive_key:"scout/nrlcom/ladder/111/2026/round-NN.json"}`.
  - Reproduce the S3 objects (`aws s3 ls` / reviewer independent check).
  - Run extraction in the `jeromelu-api` container (the Phase 3.5 `docker cp scripts → /runtmp` procedure; clean up after): `python -m scripts.data.populate_db_from_s3 --phase standings --seasons 2026` and `--phase injuries`. Verify `SELECT count(*) FROM team_standings WHERE season=2026` > 0 (≈17/round) and `SELECT count(*) FROM injuries WHERE source='nrl.com/casualty-ward'` > 0; spot-check team_id resolution is mostly non-null. (One casualty snapshot can only *insert* open injuries — resolution detection needs ≥2 snapshots; that's expected and fine for the seed.)
- **Tests:** unit drift (`test_models.py` ×2) + extractor units (`test_phase_aux.py`) run in CI by default; live drift (`test_response_shape.py` ×2) under `SCOUT_DRIFT_LIVE=1` only. Each route's `validated:true` / 500-on-drift is proven by construction (route calls the identical `model_validate`, exercised green via live + red via a deliberate model-break that is reverted), consistent with the Phase 3 proof level.
- **Cron:** `bash -n scripts/scout-refresh.sh` clean; dry-run shows the two correct URLs (single quoted arg, no unquoted `&`); cron lines have 5 timing fields + `ubuntu` + absolute path. First scheduled fire is operator/time-gated (deferred, mirrors Phase 3 TASK-12).
- **worker-scraper:** after deletion, `grep -rn "worker-scraper\|worker_scraper"` returns only `docs/archive/prd/` (historical) — no code, compose, CI, deploy, or live-doc references; `make -n` and the api import path are unaffected.

**Documentation updates:**
- `docs/agents/crew/scout/roadmap.md` — Phase 4 heading → ✅ Shipped (note extractor stays manual/backfill + the scheduled-extraction follow-up); strike the worker-scraper retirement line as done.
- `docs/agents/crew/scout/charter.md` — pipeline-inventory Status cells for `nrlcom_casualty_ward` + `nrlcom_ladder` → ingest shipped (Phase 4) + extractor live; D4 → worker-scraper retired; D13 extractor inventory (`extract_injuries`/`extract_ladder` no longer pending).
- `services/api/app/scout/nrlcom_casualty_ward/README.md` + `nrlcom_ladder/README.md` — flip "DB extraction: **Deferred**" → the live `phase_aux` extractor + phase name; add a `## Tests` section (unit + live drift, like the draw README); confirm cadence row matches the new cron.
- `docs/agents/system/scraper.md` — mark the `worker-scraper` Temporal worker **retired/deleted** (the doc already framed it as marked-for-retirement).
- `docs/agents/system/README.md`, `docs/agents/crew/scout/README.md`, `docs/architecture/08-technology-stack.md`, `docs/pages/wiki/data-feeds.md` — remove or flip live references to the worker-scraper service. (`docs/archive/prd/jeromelu-ai-scraper-prd.md` is a historical archive — leave it.)
- `scripts/data/populate/README.md` — note the `injuries` + `standings` phases now have pure-extractor unit coverage (Phase 4).
- Data docs trinity (per project memory `project_data_docs_trinity`): verify/refresh the `injuries` and `team_standings` entries under `docs/operations/data-catalogue/`, `data-lineage/`, `data-sources/` so the extractor + source are referenced (create if missing — one file per table per the trinity convention).
- **Run report (completion condition):** `docs/build/runs/2026-05-28-scout-phase-4-casualty-ladder.md` + a row in `docs/build/runs/README.md`.

**Tasks:** TASK-21 … TASK-28 (see [TASKS.md](./TASKS.md)).

## Completed work

Completed plans are **not** archived in this file. When a plan's tasks are all done, its durable record is a run report under [`docs/build/runs/`](./runs/) (see the [index](./runs/README.md)) and the plan is removed from "Active plan" above. This document holds only active/future plans; the run reports are the system of record for what shipped.
