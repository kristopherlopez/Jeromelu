# Scout Phase 3 — nrl.com draw + match-centre ingest hardening

**Date:** 2026-05-24 · **Status:** 🟡 In progress (TASK-07 of TASK-07→12 done) · **Plan:** Scout Phase 3 (PLAN.md)

**TL;DR** — The draw + match-centre ingest pipelines already existed (fetch → S3 archive → audit) but lacked charter discipline. Phase 3 hardens them: D8 envelope models, strict-parse wired into the routes, fixtures + unit/live drift tests, daily-during-round cron, seed. NRL only (comp 111), forward-only; DB extractors deferred to Phase 3.5.

---

## What was completed

### TASK-07 — nrlcom_draw: D8 models + fixture + unit drift tests (`f02a678`)
Captured the live `/draw/data` canonical response (comp 111, current season — 5 fixtures, all `FullTime`/`Post`-capable, pretty-printed, 1749 lines / 58KB) to `tests/fixtures/scout/nrlcom_draw/canonical_response.json`. Created `services/api/app/scout/nrlcom_draw/models.py` with two strict models (`extra="forbid"`): `NrlcomDraw` (envelope, 14 top-level keys) and `DrawFixture` (`matchCentreUrl: str` load-bearing + 12 other keys; team/clock/CTA objects opaque). `disclaimer` typed `str | None` per plan (non-load-bearing copyright string; the key is still required so a rename/removal still trips drift, but a null value won't 500 the daily cron). Added `tests/unit/api/scout/test_nrlcom_draw_models.py` (templated on the settings unit test): canonical parse + three negatives (unknown top-level, unknown fixture field, missing `matchCentreUrl`).
**Proof:** `pytest tests/unit/api/scout/test_nrlcom_draw_models.py` → 4 passed; full scout unit suite → 35 passed (no regression). Reviewer **PASS WITH CONCERNS** — both non-blocking: `disclaimer` typing aligned to plan (`str | None`) after review; proof recorded here per the run-report ritual.

---

## How we know it's done (running)
- Unit drift tests green in CI; live drift tests (TASK-08/10) hit real nrl.com under `SCOUT_DRIFT_LIVE=1`.

## Decisions & deviations
- `callToAction`/`secondaryCallToAction` typed `dict[str, Any] | None` (CTAs vary by match state across rounds); `disclaimer` `str | None`. Load-bearing `matchCentreUrl` is strictly required.

## Outstanding
- ☐ TASK-08 — wire strict-parse into the draw route + live drift test.
- ☐ TASK-09 — match-centre D8 envelope model + fixture + unit tests.
- ☐ TASK-10 — match-centre route wiring (non-aborting) + round-optional resolution + live test.
- ☐ TASK-11 — daily cron (scout-refresh.sh + cron.d).
- ☐ TASK-12 — prod seed + S3 verify + docs; finalise this report + clear the plan.

## Commits
`f02a678` (TASK-07).
