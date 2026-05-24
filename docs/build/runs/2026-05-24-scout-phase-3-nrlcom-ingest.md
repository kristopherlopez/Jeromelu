# Scout Phase 3 — nrl.com draw + match-centre ingest hardening

**Date:** 2026-05-24 · **Status:** 🟡 In progress (TASK-07, 08 of TASK-07→12 done) · **Plan:** Scout Phase 3 (PLAN.md)

**TL;DR** — The draw + match-centre ingest pipelines already existed (fetch → S3 archive → audit) but lacked charter discipline. Phase 3 hardens them: D8 envelope models, strict-parse wired into the routes, fixtures + unit/live drift tests, daily-during-round cron, seed. NRL only (comp 111), forward-only; DB extractors deferred to Phase 3.5.

---

## What was completed

### TASK-07 — nrlcom_draw: D8 models + fixture + unit drift tests (`f02a678`)
Captured the live `/draw/data` canonical response (comp 111, current season — 5 fixtures, all `FullTime`/`Post`-capable, pretty-printed, 1749 lines / 58KB) to `tests/fixtures/scout/nrlcom_draw/canonical_response.json`. Created `services/api/app/scout/nrlcom_draw/models.py` with two strict models (`extra="forbid"`): `NrlcomDraw` (envelope, 14 top-level keys) and `DrawFixture` (`matchCentreUrl: str` load-bearing + 12 other keys; team/clock/CTA objects opaque). `disclaimer` typed `str | None` per plan (non-load-bearing copyright string; the key is still required so a rename/removal still trips drift, but a null value won't 500 the daily cron). Added `tests/unit/api/scout/test_nrlcom_draw_models.py` (templated on the settings unit test): canonical parse + three negatives (unknown top-level, unknown fixture field, missing `matchCentreUrl`).
**Proof:** `pytest tests/unit/api/scout/test_nrlcom_draw_models.py` → 4 passed; full scout unit suite → 35 passed (no regression). Reviewer **PASS WITH CONCERNS** — both non-blocking: `disclaimer` typing aligned to plan (`str | None`) after review; proof recorded here per the run-report ritual.

### TASK-08 — nrlcom_draw: wire strict-parse into the route + live drift test (`a0ecbd7`)
Wired the D8 contract into the route: `services/api/app/scout/nrlcom_draw/routes.py` now calls `NrlcomDraw.model_validate(data)` **after** `archive_response(...)` (raw captured first), sets `detail["validated"] = True` on success, and adds an `except ValidationError → HTTPException(500)` + failed-audit arm ordered before the generic `except Exception` (the `NrlcomDrawFetchError → 502` path is unchanged). Added `tests/integration/scout/test_nrlcom_draw_response_shape.py` — env-flagged (`SCOUT_DRIFT_LIVE=1`) live drift test.
**Proof:** skip mode → 1 skipped (exact reason string); live mode → 1 passed against real nrl.com; deliberate model-break (`is_replay: bool` added to `NrlcomDraw`) → live test failed naming `is_replay`, then reverted (`models.py` no diff). The route's `validated:true` / 500-on-drift behaviour is proven by construction — the route calls the identical `NrlcomDraw.model_validate`, exercised green (live) and red (deliberate break); not separately re-run against a live API server. Reviewer **PASS WITH CONCERNS** — non-blocking (run-report update [done here]; live test is calendar-sensitive in the pre-season window, in-scope as written).

---

## How we know it's done (running)
- Unit drift tests green in CI; live drift tests (TASK-08/10) hit real nrl.com under `SCOUT_DRIFT_LIVE=1`.

## Decisions & deviations
- `callToAction`/`secondaryCallToAction` typed `dict[str, Any] | None` (CTAs vary by match state across rounds); `disclaimer` `str | None`. Load-bearing `matchCentreUrl` is strictly required.

## Outstanding
- ☐ TASK-09 — match-centre D8 envelope model + fixture + unit tests.
- ☐ TASK-10 — match-centre route wiring (non-aborting) + round-optional resolution + live test.
- ☐ TASK-11 — daily cron (scout-refresh.sh + cron.d).
- ☐ TASK-12 — prod seed + S3 verify + docs; finalise this report + clear the plan.

## Commits
`f02a678` (TASK-07) · `a0ecbd7` (TASK-08).
