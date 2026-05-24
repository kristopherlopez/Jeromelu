# Scout Phase 3 — nrl.com draw + match-centre ingest hardening

**Date:** 2026-05-24 · **Status:** 🟡 In progress (TASK-07–10 of TASK-07→12 done; cron + seed remain) · **Plan:** Scout Phase 3 (PLAN.md)

**TL;DR** — The draw + match-centre ingest pipelines already existed (fetch → S3 archive → audit) but lacked charter discipline. Phase 3 hardens them: D8 envelope models, strict-parse wired into the routes, fixtures + unit/live drift tests, daily-during-round cron, seed. NRL only (comp 111), forward-only; DB extractors deferred to Phase 3.5.

---

## What was completed

### TASK-07 — nrlcom_draw: D8 models + fixture + unit drift tests (`f02a678`)
Captured the live `/draw/data` canonical response (comp 111, current season — 5 fixtures, all `FullTime`/`Post`-capable, pretty-printed, 1749 lines / 58KB) to `tests/fixtures/scout/nrlcom_draw/canonical_response.json`. Created `services/api/app/scout/nrlcom_draw/models.py` with two strict models (`extra="forbid"`): `NrlcomDraw` (envelope, 14 top-level keys) and `DrawFixture` (`matchCentreUrl: str` load-bearing + 12 other keys; team/clock/CTA objects opaque). `disclaimer` typed `str | None` per plan (non-load-bearing copyright string; the key is still required so a rename/removal still trips drift, but a null value won't 500 the daily cron). Added `tests/unit/api/scout/test_nrlcom_draw_models.py` (templated on the settings unit test): canonical parse + three negatives (unknown top-level, unknown fixture field, missing `matchCentreUrl`).
**Proof:** `pytest tests/unit/api/scout/test_nrlcom_draw_models.py` → 4 passed; full scout unit suite → 35 passed (no regression). Reviewer **PASS WITH CONCERNS** — both non-blocking: `disclaimer` typing aligned to plan (`str | None`) after review; proof recorded here per the run-report ritual.

### TASK-08 — nrlcom_draw: wire strict-parse into the route + live drift test (`a0ecbd7`)
Wired the D8 contract into the route: `services/api/app/scout/nrlcom_draw/routes.py` now calls `NrlcomDraw.model_validate(data)` **after** `archive_response(...)` (raw captured first), sets `detail["validated"] = True` on success, and adds an `except ValidationError → HTTPException(500)` + failed-audit arm ordered before the generic `except Exception` (the `NrlcomDrawFetchError → 502` path is unchanged). Added `tests/integration/scout/test_nrlcom_draw_response_shape.py` — env-flagged (`SCOUT_DRIFT_LIVE=1`) live drift test.
**Proof:** skip mode → 1 skipped (exact reason string); live mode → 1 passed against real nrl.com; deliberate model-break (`is_replay: bool` added to `NrlcomDraw`) → live test failed naming `is_replay`, then reverted (`models.py` no diff). The route's `validated:true` / 500-on-drift behaviour is proven by construction — the route calls the identical `NrlcomDraw.model_validate`, exercised green (live) and red (deliberate break); not separately re-run against a live API server. Reviewer **PASS WITH CONCERNS** — non-blocking (run-report update [done here]; live test is calendar-sensitive in the pre-season window, in-scope as written).

### TASK-09 — nrlcom_match_centre: D8 envelope model + fixtures + unit drift tests (`45fd6fe`)
**Key finding:** the match-centre envelope is **match-state-dependent** (verified live). A `FullTime` match carries 7 result-only top-level keys (`attendance`, `officials`, `positionGroups`, `timeline`, `weather`, `groundConditions`, `imageUrl`); an `Upcoming` match omits those and instead carries `broadcastChannels`/`videoProviders`; 22 keys are shared. So `NrlcomMatchCentre` (envelope-only, `extra="forbid"`) is a **union**: 22 shared required + 9 state-dependent optional (31-key union). Deep internals (lineups, ~58-field stats, 100+ timeline events) stay opaque `dict`/`list`.
Captured **two** fixtures — `canonical_response.json` (FullTime, ~196KB) and `canonical_response_upcoming.json` (Upcoming, ~15KB). Added `tests/unit/api/scout/test_nrlcom_match_centre_models.py` with **4** tests (one more than the 3 specified): canonical (FullTime) parse, **upcoming parse** (proves the union accepts both states), unknown-top-level negative (`is_replay`), missing-`matchId` negative.
**Deviation from spec (evidence-driven, reviewer-approved):** spec said 1 fixture / 3 tests / "~29 keys"; shipped 2 fixtures / 4 tests / 31-key union. Reason: a FullTime-only model would 500 every upcoming match the daily cron (TASK-10/11) walks. Reviewer independently confirmed `extra="forbid"` still trips on a genuinely novel key outside the union — the D8 guard survives the widening.
**Proof:** `pytest tests/unit/api/scout/test_nrlcom_match_centre_models.py` → 4 passed; full scout unit suite → 39 passed (no regression). Reviewer **PASS WITH CONCERNS** — all non-blocking (deviation recorded here; mutual-exclusivity of state-key groups intentionally not enforced — envelope guard, not a state machine; proof recorded here).

### TASK-10 — nrlcom_match_centre: route strict-parse (non-aborting) + round-optional + live drift test (`f92d4bd`)
Wired the D8 contract into the route + made the daily cron viable:
- **round optional** on the endpoint and `run_nrlcom_match_centre`; when omitted it resolves the current round from the draw's `selectedRoundId` (recorded as `detail.resolved_round`; `HTTPException(502)` if unresolvable) — resolved **before** the `round-{NN}` S3 path is built.
- **Per-match strict-parse**: each match is `NrlcomMatchCentre.model_validate`'d after archiving; a `ValidationError` is appended to a new `validation_failures` list and does **not** abort the round walk (one bad match shouldn't lose the rest). Surfaced in `detail` + the completed `summary_text`.
- Relaxed the `scout-nrlcom-match-centre` Makefile target — `ROUND` now optional (`$(if $(ROUND),&round=$(ROUND))`, `ifndef SEASON` kept).
- Added `tests/integration/scout/test_nrlcom_match_centre_response_shape.py` (env-flagged live drift test).
**Proof:** route imports clean; `make -n scout-nrlcom-match-centre SEASON=2026` (no ROUND) → URL with no `&round=`, no error; skip → 1 skipped; live → 1 passed; deliberate model-break (`is_replay`) → live test failed naming it, reverted (`models.py` no diff). The end-to-end run (`resolved_round` set, `matches_archived ≥ 1`, `validation_failures` populated) is verified **by construction** (route calls the identical, live-exercised `model_validate`; round resolution is straight-line) and will be exercised at TASK-12's prod seed (round omitted). Reviewer **PASS WITH CONCERNS** — proof level ruled acceptable (same split as TASK-08); non-blocking: 502-message superset + `str(e)[:300]` truncation (defensive, audit-row size); doc update scheduled to TASK-12.

---

## How we know it's done (running)
- Unit drift tests green in CI; live drift tests (TASK-08/10) hit real nrl.com under `SCOUT_DRIFT_LIVE=1`.

## Decisions & deviations
- `callToAction`/`secondaryCallToAction` typed `dict[str, Any] | None` (CTAs vary by match state across rounds); `disclaimer` `str | None`. Load-bearing `matchCentreUrl` is strictly required.

## Outstanding
- ☐ TASK-11 — daily cron (scout-refresh.sh + cron.d).
- ☐ TASK-12 — prod seed + S3 verify + docs; finalise this report + clear the plan.

## Commits
`f02a678` (TASK-07) · `a0ecbd7` (TASK-08) · `45fd6fe` (TASK-09) · `f92d4bd` (TASK-10).
