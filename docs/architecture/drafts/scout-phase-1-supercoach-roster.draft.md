---
tags: [area/architecture, subarea/agents]
status: draft
---

# Scout Phase 1 — SuperCoach Roster (Implementation Plan)

> Draft. Last reviewed: 2026-05-12.
>
> Step-by-step plan for Phase 1 of the [Scout charter expansion](scout-charter-expansion.draft.md): bring the SuperCoach roster pipeline into compliance with the locked decisions (D1–D8). The proof slice that sets the pattern for Phases 2–4.

---

## What this plan is for

The Scout charter draft describes Phase 1 as a deliverables list. This doc translates that into an ordered, verifiable sequence of steps with file paths, code shapes, and per-step verification commands. It's the document an implementer (you, me, a future session) opens and works against.

---

## State summary (the good news)

Phase 1 is **smaller than expected** because most of the SuperCoach roster path is already production code:

| Surface | Where it lives today | Status |
|---|---|---|
| Fetcher (calls supercoach.com.au) | `packages/shared/jeromelu_shared/players/supercoach.py` → `fetch_supercoach_roster()` | ✅ shipped |
| CLI wrapper | `scripts/data/fetchers/fetch_supercoach_players.py` | ✅ shipped (thin wrapper) |
| SCD-2 diff logic | `packages/shared/jeromelu_shared/players/roster.py` → `seed_roster()` / `refresh_roster()` | ✅ shipped |
| Local seed | `scripts/data/seed_players_prod.py` + `make seed-players` | ✅ shipped |
| Prod seed endpoint | `POST /api/admin/players/seed` | ✅ shipped |
| Prod refresh endpoint | `POST /api/admin/players/refresh` (accepts JSON payload) | ✅ shipped |
| Server-side fetch + refresh | `POST /api/admin/players/fetch-and-refresh` (one call) | ✅ shipped (per fetcher docstring) |
| Make targets | `fetch-players`, `seed-players`, `prod-seed-players`, `prod-refresh-players` | ✅ shipped |
| Skill | `.claude/skills/scrape-supercoach/skill.md` | ✅ shipped (to be retired) |
| `agent_id='scout'` CHECK constraint allows it | `agent_runs.ck_agent_runs_agent_id` confirmed via DB query | ✅ ready |

**`agent_id='stats'` and `agent_id='fixtures'` also exist** in the constraint as historical reservations from the now-retired scraper.md plans. Per D6 of the charter, all new pipelines use `agent_id='scout'` with `detail_json.pipeline=<name>`. The orphan IDs are left in place for back-compat; cleanup is a separate housekeeping pass.

## Gap analysis

What's missing to make the SuperCoach roster pipeline charter-compliant:

| Gap | Charter clause | Phase 1 step |
|---|---|---|
| No `agent_runs` audit row per invocation | D6 (single agent_id with pipeline discriminator) | Steps 4–6 |
| No drift fixture or shape test | D8 (test-fail, never silent-adapt) | Steps 7–10 |
| Endpoint lives under `/players/*`, not `/scout/*` | Charter naming convention | Step 11 (alias) |
| `make` target uses `prod-refresh-players` not `scout-supercoach-roster` | Charter naming convention | Step 12 (alias) |
| `scrape-supercoach` skill exists | D5 (no skills for deterministic fetchers) | Step 13 |
| No cron schedule | D3 (external cron) | Step 14 |
| Existing operations don't yet route through the new endpoint | D2 (single Scout identity for all acquisition) | Step 15 (cutover) |

---

## Implementation steps

Each step lists its target files, the change in shape, and a verification command. **No step depends on a later one for correctness** — each is independently testable. Stop and surface issues if any verification fails before continuing.

### Step 1 — Verify the existing `/api/admin/players/fetch-and-refresh` endpoint works

Before any changes, confirm the existing path is healthy.

- **Verify:** read `services/api/app/routers/players.py` and confirm `/fetch-and-refresh` exists and returns a success structure. If the fetcher docstring lies about this endpoint, **stop and surface — the docstring may be aspirational**.
- **Verify (live):** `curl -X POST $LOCAL_API/api/admin/players/fetch-and-refresh -H "X-Admin-Key: $ADMIN_KEY"` returns 200 with non-zero player counts.

### Step 2 — Read and document the current SCD-2 refresh path

Understanding what the endpoint actually does before wrapping it.

- **Read:** `packages/shared/jeromelu_shared/players/roster.py` — `refresh_roster()`. Note what it reads, what it writes, idempotency story.
- **Read:** `packages/shared/jeromelu_shared/players/supercoach.py` — `fetch_supercoach_roster()`. Note the response shape, any current Pydantic models, error types.
- **Output:** one paragraph in commit message of the implementing PR summarising the data flow. Not a separate doc.

### Step 3 — Verify `agent_audit` shape

The Scout media-discovery loop already uses this. Confirm the API.

- **Read:** `packages/shared/jeromelu_shared/agent_audit.py`. Note the public surface — likely `record_agent_started(...)` and `record_agent_ended(...)` returning a `run_id`.
- **Read:** how `services/api/app/scout/loop.py` calls it — that's the canonical usage pattern.
- **Verify:** confirm `detail_json` is a free-form JSONB the wrapper writes to (per D6, this is where `pipeline='supercoach-roster'` goes).

### Step 4 — Create the `scout/supercoach_roster/` folder + audit wrapper

The first behavioural change. Per D9, the new pipeline lives in its own folder. Wraps the existing endpoint logic; no fetch-or-persist changes.

- **New folder:** `services/api/app/scout/supercoach_roster/` with `__init__.py`, `routes.py`, `README.md`. (`fetcher.py` and `models.py` land in later steps as needed; thin wrapper is fine for now since the fetcher lives in `jeromelu_shared.players.supercoach`.)
- **In `routes.py`:** define `POST /api/admin/scout/supercoach-roster`. Implementation wraps the existing `/api/admin/players/fetch-and-refresh` handler logic in `record_agent_started(agent_id='scout', detail_json={'pipeline': 'supercoach-roster', 'mode': 'fetch-and-refresh'})` → call existing logic → `record_agent_ended(run_id, status='ok'|'error', detail_json={...counts...})`.
- **Counts to record in `detail_json` on completion:** `players_seen`, `players_inserted`, `players_updated_team`, `players_updated_position`, any other counts the SCD-2 logic produces.
- **In `README.md`:** record source (supercoach.com.au players-cf endpoint), cadence (daily), natural key (`external_id` on `people`), owner (Scout).
- **Wire the router** into the FastAPI app where other admin routers are mounted.
- **Verify:** run the endpoint → confirm one new row in `agent_runs` with `agent_id='scout'`, `detail_json->>'pipeline' = 'supercoach-roster'`, `status='completed'`, non-null cost columns (likely $0.00).

### Step 5 — Add audit-row response to the endpoint

So the caller (cron, `make` target, operator) gets a `run_id` to track.

- **Change:** endpoint response includes `{"run_id": "<uuid>", ...existing counts}`.
- **Verify:** repeat Step 4's curl; response carries `run_id` that matches the `agent_runs` row inserted.

### Step 6 — Unit test the audit wrapper

Without the LLM, without the live API. Test folder mirrors source folder per D9.

- **File:** `tests/unit/api/scout/supercoach_roster/test_routes_audit.py`
- **Shape:** mock `fetch_supercoach_roster` to return a small fixture; call the endpoint; assert one `agent_runs` row is written with the expected `agent_id`, `pipeline`, counts.
- **Verify:** `pytest tests/unit/api/scout/supercoach_roster/` passes.

### Step 7 — Capture the canonical-response fixture (D8 step 1)

Snapshot what the upstream returns *right now*.

- **Action:** run `python scripts/data/fetchers/fetch_supercoach_players.py` against the live endpoint. Capture the resulting JSON.
- **Trim:** to a small representative sample (3–5 player rows from each team) for fixture stability and review-ability. The drift test cares about *shape* not row count.
- **File:** `tests/fixtures/scout/supercoach_roster/canonical_response.json` — the trimmed sample, checked in. (Snake-case folder per D9 naming convention — Python identifier consistency.)
- **Verify:** the fixture is valid JSON, ≥1 player per team in the sample.

### Step 8 — Add strict Pydantic models for the response (D8 step 2)

Models live inside the pipeline folder per D9, not in the shared package.

- **File:** `services/api/app/scout/supercoach_roster/models.py`
- **Change:** define `SuperCoachPlayer(BaseModel)` with explicit fields matching the fixture; `Config.extra = 'forbid'` so unknown fields raise.
- **Change:** the pipeline's `fetcher.py` (also in the folder) wraps `jeromelu_shared.players.supercoach.fetch_supercoach_roster` and parses the result through the strict model before returning. The shared package stays unchanged — strict parsing is a Scout-layer concern; transcript-cleaning and other consumers of the shared package don't need it.
- **Verify:** `python -c "from app.scout.supercoach_roster.fetcher import fetch; fetch(season=2026)[0]"` returns a Pydantic instance.

### Step 9 — Add the drift test (D8 step 3)

- **File:** `tests/integration/scout/supercoach_roster/test_response_shape.py`
- **Default mode (CI-safe):** loads `tests/fixtures/scout/supercoach_roster/canonical_response.json`, parses with the Pydantic model. Asserts no errors.
- **Live mode (env-flagged):** when `SCOUT_DRIFT_LIVE=1`, hits the real endpoint and parses. Same assertion.
- **Verify (fixture mode):** `pytest tests/integration/scout/supercoach_roster/` passes.
- **Verify (live mode):** `SCOUT_DRIFT_LIVE=1 pytest tests/integration/scout/supercoach_roster/` passes against a healthy upstream.

### Step 10 — Add intentionally-broken-fixture variant to prove the drift test fails on drift

A negative test — without it, we don't know the drift detection actually triggers.

- **File:** `tests/integration/scout/supercoach_roster/test_response_shape.py` adds a test that takes the canonical fixture, injects an unknown field, and asserts that parsing raises a Pydantic `ValidationError`.
- **Verify:** the negative test passes (parsing the broken fixture raises).

### Step 11 — Mark the legacy `/api/admin/players/fetch-and-refresh` as deprecated alias

Step 4 already created the new `POST /api/admin/scout/supercoach-roster` route in `scout/supercoach_roster/routes.py`. The legacy path stays live for back-compat but is marked deprecated.

- **File:** `services/api/app/routers/players.py`
- **Change:** add a code comment marking `/fetch-and-refresh` as a deprecated alias; optionally have it call into the new Scout route handler instead of duplicating logic.
- **Verify:** both `curl -X POST $LOCAL_API/api/admin/scout/supercoach-roster -H "X-Admin-Key: $ADMIN_KEY"` and `curl -X POST $LOCAL_API/api/admin/players/fetch-and-refresh -H "X-Admin-Key: $ADMIN_KEY"` return the same shape and both produce `agent_runs` rows.

### Step 12 — Add `make scout-supercoach-roster` target

Charter D5 says ad-hoc operator runs use the endpoint or a make target — not a skill.

- **File:** `Makefile`
- **Change:** add
  ```
  scout-supercoach-roster:
      curl -s -X POST $(PROD_API)/api/admin/scout/supercoach-roster \
          -H "X-Admin-Key: $(ADMIN_KEY)"
  ```
- Optionally: a `LOCAL` variant for local testing using `$(LOCAL_API)`.
- **Verify:** `make scout-supercoach-roster ADMIN_KEY=$ADMIN_KEY` works against local and prod.

### Step 13 — Retire the `scrape-supercoach` skill

Per D5.

- **Delete:** `.claude/skills/scrape-supercoach/skill.md` (and the directory if empty).
- **Update any docs that reference the skill** — likely `docs/agents/system/player-roster.md` (mentioned in the skill body), MEMORY.md if relevant.
- **Verify:** `grep -r scrape-supercoach docs/ .claude/` returns no hits (other than expected historical references in the charter draft itself).

### Step 14 — Schedule daily cron

External cron per D3.

- **Determine:** where does Scout's daily YouTube refresh cron currently live? (Per `scout.md` §3.4 there's a daily job — likely an external cron entry, a Render/Lightsail scheduled task, or a documented `crontab` invocation.)
- **Add:** an equivalent entry for `make scout-supercoach-roster` once daily (suggested: 06:30 AET, after the YouTube refresh window).
- **Verify:** the cron entry is documented (in the same place the YouTube cron lives) and a manual test run produces an `agent_runs` row.

### Step 15 — Cutover and observe

The shift from "operator runs `make fetch-players` then `make seed-players`" to "Scout endpoint runs daily."

- **Update:** any internal docs that reference the old two-step flow as the canonical path (point them at the endpoint / make target instead).
- **Observe:** watch the first 3 daily runs. Check:
  1. `agent_runs` row created each time with `status='completed'`.
  2. Drift test (live mode) green in CI.
  3. `people` row count moves when upstream changes, stable when it doesn't (idempotency per D7).
- **Document any anomalies** — this is the bake-in period before extending the pattern to Phase 2.

---

## Acceptance criteria

Phase 1 is **done** when all of these are true:

1. `POST /api/admin/scout/supercoach-roster` exists (handled by `services/api/app/scout/supercoach_roster/routes.py`), writes an `agent_runs` row, returns `run_id` + counts.
2. `services/api/app/scout/supercoach_roster/` folder exists with `__init__.py`, `routes.py`, `models.py`, `README.md` (and `fetcher.py` if non-trivial wrapping is needed).
3. `tests/fixtures/scout/supercoach_roster/canonical_response.json` is checked in.
4. `pytest tests/unit/api/scout/supercoach_roster/ tests/integration/scout/supercoach_roster/` is green in CI.
5. `SCOUT_DRIFT_LIVE=1 pytest tests/integration/scout/supercoach_roster/` is green against the live upstream.
6. The drift negative test (broken fixture) fails parsing as expected.
7. `make scout-supercoach-roster` works from local and prod.
8. `.claude/skills/scrape-supercoach/` is deleted.
9. A daily cron is scheduled and has produced at least one `agent_runs` row.
10. After 3 days of observation, `people`/`player_attributes` are healthy and no drift-test failures.

---

## Rollback strategy

If Phase 1 lands a regression in roster data:

1. **Disable the cron** — comment out the entry; manual operator runs only.
2. **Revert the endpoint alias** — old `/api/admin/players/fetch-and-refresh` endpoint stays live throughout; nothing else writes to people/player_attributes via the new path until cutover.
3. **The fetch + SCD-2 logic is unchanged** — the underlying shared package functions are not touched in Phase 1. Audit-wrapper + Pydantic-strict + alias + cron are all reversible.
4. **The drift test is additive** — never blocks a write; failure just surfaces to the operator.

Any rollback should be a single `git revert` of the Phase 1 PR(s).

---

## Open questions (surface during execution)

1. **Does `/api/admin/players/fetch-and-refresh` actually exist?** The fetcher docstring claims it does. If it doesn't, Step 1 fails — and Phase 1 expands to include adding the endpoint first. Verify before assuming.
2. **Where does the existing Scout daily cron live?** Step 14 depends on knowing this. If there's no current cron infrastructure on the prod box, scheduling decisions need their own mini-design.
3. **Do `agent_id='stats'` and `agent_id='fixtures'` need to be migrated to `agent_id='scout'`?** Per D6 the new pipelines use `scout`. The orphans are back-compat reservations; not a blocker for Phase 1 but worth a follow-up housekeeping pass before Phase 2's stats work.
4. **The `data/players.yaml` consumer.** The skill regenerates `data/players.yaml` (used by the transcript-cleaning pipeline). If the Scout endpoint doesn't also regenerate this file, the transcript-cleaning pipeline drifts. Either: (a) the endpoint regenerates yaml as a side effect, (b) `make scout-supercoach-roster` chains the yaml regeneration, (c) the yaml is retired and the cleaning pipeline reads from the DB instead. Decide before Step 14.
5. **Live drift-mode in CI.** Running the live-mode drift test in CI means CI depends on the upstream being available. Either: (a) run live mode in a separate scheduled CI job (not on every PR), (b) run live mode only locally on demand. (a) is the operational pattern.

---

## What this plan does NOT cover

Out of scope for Phase 1 — these belong to Phases 2+ or are addressed by other docs:

- **SuperCoach per-round stats** (`player_rounds`) — Phase 2.
- **NRL.com fetchers** — Phases 3–4.
- **Retiring `services/worker-scraper/`** — Phase 4.
- **Unified Scout dashboard** — Phase 5.
- **Live-mode drift CI scheduling** — operational follow-up.
- **Cleaning up `agent_id='stats'`/`fixtures'` reservations** — housekeeping pass.

---

## Drafting notes (delete before merge)

The real revelation in scoping Phase 1 was that most of the work is *already shipped* — the fetcher, the SCD-2 refresh, the prod endpoint, the make targets, the skill. The actual Phase 1 work is **a thin retrofit** to bring the existing pipeline into charter compliance: audit row + drift test + naming + cron. That's a tighter scope than the bullet list in the charter draft suggested, and should land in well under a day of focused work.

The two things worth being careful about are (1) **verifying the `/fetch-and-refresh` endpoint actually exists** before relying on it (Step 1) and (2) the **`data/players.yaml` side-effect** (Open Question 4) — that file feeds the transcript-cleaning pipeline downstream, and if the cutover breaks the yaml regeneration without anyone noticing, transcript cleaning silently regresses.

The plan is deliberately step-by-step at the level "do this, verify this works, then do the next thing" so any session executing it can stop and surface findings without losing context.
