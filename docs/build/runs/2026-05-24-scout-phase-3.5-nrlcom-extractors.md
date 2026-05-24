# Scout Phase 3.5 — nrl.com match-centre DB extractors (harden + verify + populate)

**Date:** 2026-05-24 · **Status:** 🟢 Shipped (TASK-13→19 done; reproducible-runtime follow-up noted) · **Plan:** Scout Phase 3.5

**TL;DR** — The S3→DB extractors for the nrl.com match-centre data already existed (`scripts/data/populate/` + orchestrator, all 6 tables + identity columns present) but had zero tests, a broken `--dry-run`, and no verified run. Phase 3.5 hardens them: fixture-based unit tests for the 4 match-centre phases (via behavior-preserving pure-function refactors), fix `--dry-run`, then populate prod + verify. NRL only (comp 111), season 2026.

---

## What was completed

### TASK-13 — make `scripts.data.populate.*` importable under pytest (`922b591`)
Prerequisite for the extractor unit tests. Added the repo root to `pytest.ini` `pythonpath` (`. services/api packages/shared`) and added package markers `scripts/__init__.py` + `scripts/data/__init__.py` (`scripts/data/populate/__init__.py` already existed) so `from scripts.data.populate.phase_matches import _extract_one` resolves under pytest. `python -m scripts.data.populate_db_from_s3` still works (regular packages). Synced the `CLAUDE.md` testing note (pythonpath now includes the repo root + a `scripts.*` import example).
**Proof:** `from scripts.data.populate.phase_matches import _extract_one` → ok; `python -m scripts.data.populate_db_from_s3 --help` → exit 0; `pytest tests/unit/` → **274 passed** (no regression). Reviewer **PASS WITH CONCERNS** — non-blocking (the CLAUDE.md enumeration sync, done here).

### TASK-14 — unit tests for `phase_matches._extract_one` (`bb32a84`)
Five fixture-based unit tests for the pure matches extractor (no refactor — `phase_matches` already exposes `_extract_one`), reusing the Phase 3 FullTime fixture (`canonical_response.json`) + fake id-maps built from the fixture's real teamIds: core-field mapping (`source`/`external_match_id`/`season=2026`/`round=12`/`grade=nrl`/`status=final`/team resolution/referee from `officials[]`), `attendance==0→None`, skip-no-team (empty map → `None`), distinct-teams guard (same id → `None`), and `_KEY_RE`/`_normalize_status`/`_GRADE_MAP`.
**Proof:** `pytest tests/unit/scripts/data/populate/test_phase_matches.py` → 5 passed; full `tests/unit/` → **279 passed** (274 + 5). Reviewer confirmed the tests are non-tautological (resolution genuinely fires; negative tests trigger the real `None` branches). **PASS WITH CONCERNS** — non-blocking (avoid staging `__pycache__`; staged the test file by explicit path).

### TASK-15 — refactor `phase_stats` → pure `_extract_stat_rows` + unit tests (`093de70`)
Behavior-preserving refactor: extracted the inlined per-player row-building from `populate_player_match_stats` into a pure `_extract_stat_rows(payload, key, match_id, team_map, player_map) -> list[dict]` (mirrors `phase_matches._extract_one`). The caller UPSERTs the returned rows via the unchanged `upsert_sql`; the `players_no_meta` diagnostic is preserved via a cheap re-walk (provably equivalent — `_build_player_meta_map` never yields an empty dict, so old `if not meta` == new `id not in player_meta`). Added 4 fixture-based unit tests (camelCase→snake `_FIELD_MAP` mapping, roster meta, identity resolution nullable, row count == stat players).
**Proof:** `pytest tests/unit/scripts/data/populate/test_phase_stats.py` → 4 passed; full `tests/unit/` → **283 passed**. **Reviewer initially BLOCKed** on the empty TASKS.md Proof-notes block → **retracted to PASS WITH CONCERNS** after confirming the run-report ritual (proof is post-review; the Format-section note says an empty block at review time is not a blocker). Same false-block as TASK-11 — recurring across fresh-context reviewers; mitigation: include a proof-timing note in future review dispatches. Non-blocking concerns: C1 test-name `_nullable` (positive half covered in the field-mapping test); C2 explicit-pathspec staging (done).

### TASK-16 — refactor `phase_team_lists` → pure `_extract_player_list_rows` + unit tests (`a9bea13`)
Behavior-preserving refactor: extracted the inlined player row-building into a pure `_extract_player_list_rows(payload, match_id, team_map, player_map) -> list[dict]` (same skip rules: unresolved team / no playerId / no person_id). Caller runs the unchanged existence pre-check + INSERT over the returned rows; `players_no_match` preserved via a resolvable-count; the coach path (`_ensure_coach_person`, DB) stays inline. Added 3 unit tests (one row per resolvable player + jersey/position/is_captain; skip-unresolved-player; skip-unresolved-team).
**Proof:** `pytest tests/unit/scripts/data/populate/test_phase_team_lists.py` → 3 passed; full `tests/unit/` → **286 passed**. Dispatched the reviewer with a proof-timing note up front (no false-block this time). **Reviewer PASS WITH CONCERNS** — C1 (non-blocking, not realisable): the interleaving change (`[all players] then [all coaches]` vs per-team) could only diverge if a coach and an opposing-team player shared one `profileId` in the same match — impossible in NRL, zero overlap in the fixture; rows are otherwise independent + idempotent.

### TASK-17 — refactor `phase_timeline` → pure timeline/official extractors + unit tests (`2082e2c`)
Behavior-preserving refactor: extracted `_extract_timeline_rows(payload, key, match_id, team_map, player_map)` (one row per `timeline[]` event — sequence, event_type default `"Unknown"`, running scores, team/player resolution) and `_extract_official_rows(payload, key, match_id)` (one row per named official, `person_id=None`). `populate_timeline_and_officials` calls both and UPSERTs via the unchanged `timeline_sql`/`officials_sql`; all counters + per-50 checkpoint + final commit + summary keys untouched. Added 4 unit tests.
**Proof:** `pytest tests/unit/scripts/data/populate/test_phase_timeline.py` → 4 passed; full `tests/unit/` → **290 passed**. **Reviewer PASS** (no concerns; clean — the proof-timing note in the dispatch prevented the recurring false-block). The 4 match-centre phases now all have pure-extractor unit coverage.

### TASK-18 — fix the broken `--dry-run` (`429f4a1`)
Closed the META known-bug (phases committed internally before the outer rollback → `--dry-run` silently wrote). Threaded `commit: bool = True` through **all 12** orchestrated phase functions; guarded **every** `db.commit()` (16 sites: finals + the per-50 checkpoints in `phase_stats`/`phase_timeline` + the in-loop commits in `phase_people`/`phase_attributes`) as `if commit: db.commit()`. The orchestrator computes `commit = not args.dry_run` and threads it into every phase call; the outer dry-run rollback is retained; `--dry-run` help updated. Flipped the META known-bug entry to FIXED. Added `test_dry_run_flag.py` — a parametrized signature test over all 12 functions.
**Proof:** `pytest test_dry_run_flag.py` → 12 passed; full `tests/unit/` → **302 passed**; `grep db.commit()` shows 0 unguarded. **Reviewer PASS WITH CONCERNS** — non-blocking: one-line-`if` style; and the **load-bearing on-box behavioral check** (`--dry-run` then `count(*)` shows no delta) is deferred to TASK-19's prod run — **TASK-19 must capture that delta** since META now publicly claims FIXED.

### TASK-19 — prod populate run + DB verification + docs (Phase 3.5 closure)
Ran the populate against prod for season 2026 and verified. The box has no standalone Python env with the ORM deps, so — having found the match tables **already populated** (612 matches across seasons, from prior dev-tunnel runs) and the `jeromelu-api` container carrying the full deps + DB + S3 + `jeromelu_shared` — I staged the (just-deployed) scripts into the container (`docker cp … jeromelu-api:/runtmp`) and ran them there with the API's exact dependency set, then cleaned up `/runtmp` (api healthy after).
- **`--dry-run` fix confirmed on-box (the TASK-18 load-bearing check):** `--phase matches --seasons 2026 --dry-run` parsed 204 matches, computed 0 inserts / 204 updates, logged "rolling back all changes", count stayed 612. Definitive proof via `last_synced_at`: BEFORE the real run it read `2026-05-16 11:07` (the *prior* real run) — **not** `12:41` when the dry-run ran → the dry-run did not commit; AFTER the real run it read `2026-05-24 12:42` (now) → the real run did. ✅
- **Real populate (`identity, rounds, matches, team_lists, stats, timeline`, `--seasons 2026`):** ran clean, no errors. identity +4 player-id mappings; matches 204 updated; team_lists +189 rows +10 coaches; stats +190 / 3040 updated; timeline 9403 updated, officials +18 / 268 updated. (Skipped `people` — it ignores `--seasons` and walks all archives; 2026's people already exist.)
- **2026 verification counts (all non-zero):** matches 204, match_team_lists 3767, player_match_stats 3230, match_timeline 9974, match_officials 286. (Lower-than-naive because ~half of 2026's 204 fixtures are Upcoming — no stats/lineups yet — consistent with mid-season.)
- **Docs:** created `scripts/data/populate/README.md` (phases, run command, pure-function test seams, the fixed `--dry-run`, the runtime caveat). The 5 match-table data-catalogue files already reference the `phase_*` extractors — no redundant edit needed.

---

## How we know it's done (running)
- Unit tier imports `scripts.data.populate.*`; extractor unit tests land in TASK-14→17.

## Decisions & deviations
- Used regular package markers (`__init__.py`) over relying on namespace packages, for an explicit, stable import chain. `-m` invocation unaffected.

## Box deploy (2026-05-24, operator-authorised)
Deployed the Phase 3.5 code + cron to the box (zero-downtime — skipped the image pull/restart since Phase 3.5 changes no container code):
- Fast-forwarded the box git working tree `cf1cddb → 7319e50` (`git -c core.fileMode=false pull --ff-only`; the only local changes were benign chmod mode-bits + an untracked `.venv-ops/`). `_extract_stat_rows` + the `commit` guards are now present on the box.
- Synced the crontab: `/etc/cron.d/jeromelu` now carries the **3 nrlcom** (Phase 3) + **5 supercoach** (Phase 2.5) lines (nrlcom was 0 before) → also unblocks the Phase 2.5 (TASK-06) and Phase 3 cron-fire verifications.

## Follow-up (not blocking — Phase 3.5 shipped)
- **Reproducible ops runtime for the populate.** TASK-19 ran via a one-off `docker cp` of the scripts into the `jeromelu-api` container (the box has no standalone env with the ORM deps). That works but isn't reproducible for future backfills/cron. Recommended durable fix: **bake `scripts/` + `packages/shared` into the api image** (Dockerfile) so `docker exec jeromelu-api python -m scripts.data.populate_db_from_s3 …` just works — or a managed ops venv. This is an infra decision for the human/planner (surfaced; not self-queued). Documented in `scripts/data/populate/README.md` § Runtime.

## Commits
`922b591` (TASK-13) · `bb32a84` (TASK-14) · `093de70` (TASK-15) · `a9bea13` (TASK-16) · `2082e2c` (TASK-17) · `429f4a1` (TASK-18). TASK-19 = the prod populate run (no code commit beyond `scripts/data/populate/README.md` + this report) — the extractor code shipped in TASK-15→18.
