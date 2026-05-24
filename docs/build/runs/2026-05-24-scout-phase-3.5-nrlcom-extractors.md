# Scout Phase 3.5 — nrl.com match-centre DB extractors (harden + verify + populate)

**Date:** 2026-05-24 · **Status:** 🟡 In progress (TASK-13 of TASK-13→19 done) · **Plan:** Scout Phase 3.5 (PLAN.md)

**TL;DR** — The S3→DB extractors for the nrl.com match-centre data already existed (`scripts/data/populate/` + orchestrator, all 6 tables + identity columns present) but had zero tests, a broken `--dry-run`, and no verified run. Phase 3.5 hardens them: fixture-based unit tests for the 4 match-centre phases (via behavior-preserving pure-function refactors), fix `--dry-run`, then populate prod + verify. NRL only (comp 111), season 2026.

---

## What was completed

### TASK-13 — make `scripts.data.populate.*` importable under pytest (`922b591`)
Prerequisite for the extractor unit tests. Added the repo root to `pytest.ini` `pythonpath` (`. services/api packages/shared`) and added package markers `scripts/__init__.py` + `scripts/data/__init__.py` (`scripts/data/populate/__init__.py` already existed) so `from scripts.data.populate.phase_matches import _extract_one` resolves under pytest. `python -m scripts.data.populate_db_from_s3` still works (regular packages). Synced the `CLAUDE.md` testing note (pythonpath now includes the repo root + a `scripts.*` import example).
**Proof:** `from scripts.data.populate.phase_matches import _extract_one` → ok; `python -m scripts.data.populate_db_from_s3 --help` → exit 0; `pytest tests/unit/` → **274 passed** (no regression). Reviewer **PASS WITH CONCERNS** — non-blocking (the CLAUDE.md enumeration sync, done here).

---

## How we know it's done (running)
- Unit tier imports `scripts.data.populate.*`; extractor unit tests land in TASK-14→17.

## Decisions & deviations
- Used regular package markers (`__init__.py`) over relying on namespace packages, for an explicit, stable import chain. `-m` invocation unaffected.

## Outstanding
- ☐ TASK-14 — unit tests for `phase_matches._extract_one`.
- ☐ TASK-15 — refactor `phase_stats` → pure `_extract_stat_rows` + tests.
- ☐ TASK-16 — refactor `phase_team_lists` → pure `_extract_player_list_rows` + tests.
- ☐ TASK-17 — refactor `phase_timeline` → pure timeline/official extractors + tests.
- ☐ TASK-18 — fix the broken `--dry-run` (commit-flag thread; close the META bug).
- ☐ TASK-19 — prod populate run + DB verify + docs; finalise this report + clear the plan.

## Commits
`922b591` (TASK-13).
