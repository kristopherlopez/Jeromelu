# Scout Phase 4 — nrl.com casualty ward + ladder (harden, schedule, seed) + retire worker-scraper

**Date:** 2026-05-28 · **Status:** 🟡 In progress · **Plan:** [PLAN.md § 2026-05-28: Scout Phase 4](../PLAN.md)

**TL;DR** — Phase 4 is a hardening replay, not greenfield: the casualty-ward + ladder ingest folders, the DB extractors (`populate_injuries` / `populate_team_standings`), the make targets, and the migrations (`031_injuries`, `059_team_standings`) all already existed. This run adds the D8 drift contract (strict envelope **and** item/stats models — deeper than draw/match-centre because the extractors are live), extractor unit tests, cron scheduling, the prod seed, and retires the orphaned `services/worker-scraper/`. NRL only (comp 111), season 2026, forward-only.

---

## What was completed

### TASK-21 — casualty-ward: D8 models + fixture + unit drift tests (`cb408c6`)
Added the D8 drift contract for the casualty-ward pipeline. Captured the live `/casualty-ward/data?competition=111` response (2026-05-28 — 99 casualties, all sharing one 8-key shape, 112KB) to `tests/fixtures/scout/nrlcom_casualty_ward/canonical_response.json`. Created `services/api/app/scout/nrlcom_casualty_ward/models.py` with two strict models (`extra="forbid"`):
- `NrlcomCasualtyWard` (envelope) — `casualties: list[Casualty]` + the 4 filter/metadata top-level keys observed live (`filterCompetitions`, `filterExpectedReturns`, `filterTeams`, `selectedCompetitionId`).
- `Casualty` (item) — modelled **strictly** (deviating from the draw/match-centre envelope-only precedent) because the live `populate_injuries` extractor reads `firstName`/`lastName`/`teamNickname`/`injury`/`expectedReturn`/`url` by exact key; a silent rename would null an `injuries` column. `firstName`/`lastName`/`teamNickname` are required non-null `str`; `injury`/`expectedReturn`/`imageUrl`/`url`/`theme` are required-present-but-nullable (`T | None`, no default — the `NrlcomDraw.disclaimer` convention). `theme` typed opaque `dict[str, Any] | None`.

Added `tests/unit/api/scout/nrlcom_casualty_ward/{__init__.py,test_models.py}` (templated on the draw test): canonical parse + 3 negatives (unknown top-level key, unknown casualty field, missing required `teamNickname`). Route wiring deliberately deferred to TASK-22.

**Proof:** `pytest tests/unit/api/scout/nrlcom_casualty_ward/test_models.py` → **4 passed**; full scout unit suite `pytest tests/unit/api/scout/` → **61 passed** (57 baseline + 4 new, no regression). Live shape verified before fixture capture: all 99 casualties share the identical 8-key set, no nulls/empties. **adversarial-reviewer: PASS WITH CONCERNS** — both non-blocking: (C1) `theme` left opaque per spec + draw precedent (extractor doesn't read it); (C2) PLAN wording floated an `expectedReturn`-null negative but the binding TASKS `What` named `teamNickname`, which is what shipped. **/simplify: no findings** (clean additive diff).

### TASK-22 — casualty-ward: wire strict-parse into route + live drift test (`bf22976`)
Wired the D8 contract into `services/api/app/scout/nrlcom_casualty_ward/routes.py`: after `archive_response(...)` (raw to S3 first), `NrlcomCasualtyWard.model_validate(data)` + `detail["validated"] = True`, and an `except ValidationError → run.fail + HTTPException(500)` arm ordered **before** the generic `except Exception`. Single-envelope abort-on-drift (the **draw** precedent, line-for-line equivalent), not the non-aborting per-match match-centre pattern; the `NrlcomCasualtyFetchError → 502` arm is unchanged. Added `tests/integration/scout/nrlcom_casualty_ward/{__init__.py,test_response_shape.py}` — env-flagged (`SCOUT_DRIFT_LIVE=1`) live drift test templated on the draw response-shape test.

**Proof:** route imports clean (`PIPELINE=nrlcom-casualty-ward`); skip mode → **1 skipped** (exact reason "Set SCOUT_DRIFT_LIVE=1 …"); live mode → **1 passed** against real nrl.com; deliberate model-break (`is_replay: bool` added to `Casualty`) → live test **failed naming `is_replay`** ("Field required"), then reverted (`git diff HEAD -- models.py` empty); full scout unit suite → **61 passed** (no regression). The route's `validated:true`/500-on-drift is proven by construction (identical `model_validate`, exercised green live + red via the reverted break) per the Phase 3 TASK-08 proof level. **adversarial-reviewer: PASS WITH CONCERNS** — both non-blocking: (C1) `validated:true`/exception-ordering has no direct route-level unit test — proven by construction, a future route unit test would harden against refactor regressions (out of scope); (C2) the live-half proof rests on the recorded run, as the proof model intends. **/simplify: no findings.**

**Harness note (not a defect):** running the unit + integration tiers in one `pytest` invocation triggers a same-package-name collection collision (both dirs hold a `nrlcom_casualty_ward` package) — a pre-existing structural pattern (draw has it too); CI runs the tiers separately, so it's a non-issue. Run tiers separately.

### TASK-23 — ladder: D8 models (alias-mapped stats) + fixture + unit drift tests (`0ba0cf6`)
Added the D8 drift contract for the ladder pipeline. Captured the live `/ladder/data?competition=111&season=2026` response (2026-05-28 — 17 positions, one 22-key stats shape, 40KB) to `tests/fixtures/scout/nrlcom_ladder/canonical_response.json`. Created `services/api/app/scout/nrlcom_ladder/models.py` with three strict models (`extra="forbid"`):
- `NrlcomLadder` (envelope) — `positions: list[LadderPosition]` + the 10 metadata top-level keys observed live (`filterCompetitions`/`filterRounds`/`filterSeasons` lists, `finalistTeams` **int**, 3 `selected*` ints, 3 `show*` bools).
- `LadderPosition` — required `teamNickname: str` (load-bearing) + `stats: LadderStats`; `clubProfileUrl`/`movement`/`next`/`theme` required-present-nullable. **No `position` field** — the upstream response has none; the extractor falls back to the enumerate index (`pos.get("position") or idx`), and a future upstream `position` would correctly trip the envelope guard.
- `LadderStats` (`populate_by_name=True`) — the 22 metrics; the 16 space-separated keys (`"points for"`, `"average winning margin"`, …) mapped via `Field(alias=...)`. 13 int, 2 float (margins), 7 str. Every field required-present-but-nullable (the casualty/`disclaimer` convention) so a removed/renamed metric trips; `extra="forbid"` catches a newly-added one.

Added `tests/unit/api/scout/nrlcom_ladder/{__init__.py,test_models.py}`: canonical parse (asserts `points_for`/`points_against`/`average_winning_margin` populate — proves the space-alias mapping reaches the Python fields) + 3 negatives (unknown top-level, unknown `stats` key, missing required `teamNickname`). Route wiring deferred to TASK-24.

**Proof:** `pytest tests/unit/api/scout/nrlcom_ladder/test_models.py` → **4 passed**; full scout unit suite → **65 passed** (61 + 4 new, no regression). All 17 positions verified to share one 6-key position shape + one 22-key stats shape before capture. **adversarial-reviewer: PASS** (no blocking concerns) — programmatically cross-checked the model field/alias set == the fixture's 22 stats keys (zero diff either direction); confirmed required-key/nullable-value contract (dropped key trips, null value tolerated), `extra="forbid"` on all three, no route wiring leaked. **/simplify: no findings.**

### TASK-24 — ladder: wire strict-parse into route + live drift test (`b405c1a`)
Wired the D8 contract into `services/api/app/scout/nrlcom_ladder/routes.py` (exact mirror of TASK-22): after `archive_response(...)`, `NrlcomLadder.model_validate(data)` + `detail["validated"] = True`, and an `except ValidationError → run.fail + HTTPException(500)` arm before the generic `except Exception`; `NrlcomLadderFetchError → 502` unchanged. Added `tests/integration/scout/nrlcom_ladder/{__init__.py,test_response_shape.py}` — env-flagged live drift test (`season=date.today().year`).

**Proof:** route imports clean (`PIPELINE=nrlcom-ladder`); skip mode → **1 skipped** (exact reason); live mode → **1 passed** against real nrl.com; deliberate break (required `tries_scored = Field(alias="tries scored")` on `LadderStats`) → live test **failed naming `positions.0.stats."tries scored"`** ("Field required"), proving the nested stats-level guard fires, then reverted (`git diff HEAD -- models.py` empty); full scout unit suite → **65 passed** (no regression). **adversarial-reviewer: PASS WITH CONCERNS** — all non-blocking (network-gated proofs accepted at the Phase 3 TASK-08 level; reviewer independently re-verified skip-mode, import, clean revert, 65-passed suite). **/simplify: no findings.**

### TASK-25 — extractor unit tests (populate_injuries + populate_team_standings) via pure-function refactor (`2675094`)
Behaviour-preserving refactor of `scripts/data/populate/phase_aux.py` to make the two Phase 4 extractors testable without S3/DB:
- `_extract_standing_rows(payload, *, key, competition, season, round_no, team_map) -> list[dict]` — one `team_standings` row per ladder position; caller UPSERTs via the unchanged `upsert_sql` with the unchanged insert/update counters.
- `_casualty_to_row(c, *, team_map, people_lookup) -> dict | None` — derived injury fields (canonical name, resolved team_id/person_id, body_part, expected-return text/round, url, key_today) or `None` on skip-no-name/no-team. The chronological open/close state machine + `_bucket_status` status derivation (current-round DB lookup) stay inline in the caller.

Added `tests/unit/scripts/data/populate/test_phase_aux.py` (9 tests): `_extract_standing_rows` (22-metric space-key→column mapping, team resolution by nickname, `ladder_position` enumerate-index fallback since upstream has no `position`, unresolved-team → None team_id but row still emitted); `_casualty_to_row` (field mapping, person lookup, skip-no-name, skip-no-team); `_bucket_status` (Round-N gap → `1_week`/`2_4_weeks`/`4_8_weeks` + no-current-round, plus `indefinite`/`tbc`/`season`/`training`/`test`/empty). Fixtures reuse the TASK-21/23 canonical captures.

**Proof:** `pytest …/test_phase_aux.py` → **9 passed**; `test_dry_run_flag.py` → **12 passed** (TASK-18 commit-guard contract holds); `python -m scripts.data.populate_db_from_s3 --help` → **exit 0** (orchestrator imports); full `pytest tests/unit/` → **341 passed** (no regression). **adversarial-reviewer: PASS** — verified behaviour preservation line-by-line (both functions byte-equivalent to the deleted inline code; UPSERT SQL/counters/commit guards untouched; `status` still caller-side); tests non-tautological. **/simplify: no findings.**

### TASK-26 — schedule cron for casualty-ward + ladder (`0eba82e`)
Added `nrlcom-casualty-ward` (`ENDPOINT="nrlcom-casualty-ward?competition=111"` — no season param, current-only) and `nrlcom-ladder` (`ENDPOINT="nrlcom-ladder?competition=111&season=$(date -u +%Y)"`) cases to `scripts/scout-refresh.sh` (mirrors the draw/match-centre cases; usage synced in both the file-header `# Usage:` and the `*)` catch-all). Added two daily lines to `scripts/cron.d/jeromelu`: casualty `30 18 * * *` (04:30 AEST), ladder `45 18 * * *` (04:45 AEST) — off-peak, no collision with the 18:00/18:15 draw/match-centre slots, positioned before the 00:30 cron-report digest so the trailing-24h report covers them.

**Proof:** `bash -n scripts/scout-refresh.sh` → clean; case simulation → `.../nrlcom-casualty-ward?competition=111` and `.../nrlcom-ladder?competition=111&season=2026` (the `&` stays inside the double-quoted `ENDPOINT`; curl uses `-X POST "$API_URL"`, so no backgrounding); both cron lines = 5 timing fields + `ubuntu` + absolute path; `grep cron.d/jeromelu scripts/lightsail-deploy.sh` → install-sync intact (lines 58-60). **adversarial-reviewer: PASS** (no concerns) — verified all 12 cross-checks incl. slot non-collision and digest ordering. **First scheduled fire is operator/time-gated** — deferred to TASK-27 closure (mirrors Phase 3 TASK-12; the box must pull past this commit, then `/var/log/jeromelu/scout-refresh.log` should show both jobs run clean after the first 18:30/18:45 UTC fire).

---

## How we know it's done (running)
- Unit drift tests green in CI; the live drift tests run under `SCOUT_DRIFT_LIVE=1`. **Both casualty-ward and ladder ingest are now fully D8-hardened** (envelope + item/stats strict-parse wired into both routes, TASK-21→24).

## Decisions & deviations
- **Casualty item modelled strictly (vs. draw/match-centre envelope-only).** Locked in the plan interview (2026-05-28): the casualty/ladder extractors are live and read nested fields by exact key, so item-level drift must fail loudly. `theme` stays opaque (not read by the extractor).

## Outstanding
- TASK-27 → TASK-28 still open (prod seed + docs, worker-scraper retirement).
- ☐ **Cron first fire (operator/time-gated).** Once the box pulls past `0eba82e`, confirm `/var/log/jeromelu/scout-refresh.log` shows `nrlcom-casualty-ward` + `nrlcom-ladder` ran clean after the first 18:30/18:45 UTC fire (mirrors the Phase 3 TASK-12 deferral; the TASK-27 seed proves the endpoints + S3 path end-to-end, this only confirms the *scheduled* invocation).

## Commits
`cb408c6` (TASK-21) · `bf22976` (TASK-22) · `0ba0cf6` (TASK-23) · `b405c1a` (TASK-24) · `2675094` (TASK-25) · `0eba82e` (TASK-26). Plus the per-task run-report/queue bookkeeping commits.
