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

---

## How we know it's done (running)
- Unit drift tests green in CI; the live drift test + route strict-parse land in TASK-22.

## Decisions & deviations
- **Casualty item modelled strictly (vs. draw/match-centre envelope-only).** Locked in the plan interview (2026-05-28): the casualty/ladder extractors are live and read nested fields by exact key, so item-level drift must fail loudly. `theme` stays opaque (not read by the extractor).

## Outstanding
- TASK-22 → TASK-28 still open (route wiring + live drift ×2, ladder models + route, extractor unit tests, cron, prod seed + docs, worker-scraper retirement).

## Commits
`cb408c6` (TASK-21). Plus the per-task run-report/queue bookkeeping commit.
