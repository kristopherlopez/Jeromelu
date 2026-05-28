# Jaromelu Task Queue

Persistent queue for the long-lived implementer session. The implementer reads top-down, completes one task at a time, dispatches `adversarial-reviewer` against the diff + task + plan, and only checks off after the review passes.

## Format

Each task is a level-3 heading with three labelled blocks:

- **What** — exactly what to do. References a section of `PLAN.md`.
- **How to verify** — concrete checks. Commands, files, expected output. Bar: "if satisfied exactly as written, the result is trustworthy."
- **Proof notes** — an optional in-flight scratchpad only. The **authoritative** proof record is the task's entry in the active run report under [`docs/build/runs/`](./runs/), written **at checkoff (after the review passes)**.

**Proof timing (important for reviewers):** under the run-report ritual, proof is recorded into the run report *at checkoff*, which is downstream of the review. So an **empty Proof-notes block at review time is expected and is NOT a blocker** — the reviewer verifies the diff against the spec and runs the **How to verify** checks itself; proof recording is a post-pass step.

Mark as `[x]` only after `adversarial-reviewer` passes. Once it passes, record what the task delivered in the active run report under [`docs/build/runs/`](./runs/) and **remove it from this file** — TASKS.md holds only the live queue, not a completed-task graveyard (see the run-report ritual in [META.md](./META.md)).

### Tags

Prefix the title with optional tags in square brackets:

- `[P0]`, `[P1]`, `[P2]`, `[P3]` — severity (from `issue-triager`)
- `[BLOCKED: reason]` — implementer hit a wall; needs human input

---

## Open tasks

> All eight tasks implement **PLAN.md § 2026-05-28: Scout Phase 4 — nrl.com casualty ward + ladder + retire worker-scraper.** Scope is NRL only (competition 111), season 2026, forward-only — historical backfill is Phase 5. The pipelines, extractors, make targets, and migrations already exist; these tasks add the D8 drift contract, extractor tests, scheduling, the seed, and retire the orphaned worker. Casualty + ladder are single-envelope fetches → drift aborts with `HTTPException(500)` (the **draw** precedent), not the non-aborting match-centre pattern.

### TASK-25 — extractor unit tests (populate_injuries + populate_team_standings) via pure-function refactor

- **What:** Per the plan's *Interface → extractor refactor* + *tests*. Behaviour-preserving refactor of `scripts/data/populate/phase_aux.py`: extract pure `_extract_standing_rows(payload, *, key, competition, season, round_no, team_map) -> list[dict]` from `populate_team_standings` (caller UPSERTs the returned rows via the unchanged `upsert_sql`; counters/commit unchanged) and pure `_casualty_to_row(c, *, team_map, people_lookup) -> dict | None` from the inner loop of `populate_injuries` (maps a casualty → the INSERT field dict; returns `None` on skip; the chronological open/close state-machine stays inline). Add `tests/unit/scripts/data/populate/test_phase_aux.py` with fixture-based tests: `_extract_standing_rows` (all 22 metrics incl. space-key→column mapping, team resolution by nickname, `position` fallback to enumerate index), `_casualty_to_row` (field mapping + skip-no-name / skip-no-team), and `_bucket_status` (Round-N gap → `1_week`/`2_4_weeks`/`4_8_weeks`, plus `indefinite`/`season`/`training`/`test`). Reuse the TASK-21/23 fixtures where helpful.
- **How to verify:** `pytest tests/unit/scripts/data/populate/test_phase_aux.py` → all passed; full `pytest tests/unit/` → no regression vs. baseline count; `python -m scripts.data.populate_db_from_s3 --help` → exit 0 (orchestrator still imports). Refactor is provably behaviour-preserving — the pure functions return exactly the dicts the inline code built; reviewer confirms no change to UPSERT SQL, counters, or commit guards (`--dry-run` signature test still passes).
- **Proof notes:** _(empty at review time)_

### TASK-26 — schedule cron for casualty-ward + ladder

- **What:** Per the plan's *Interface → cron/scheduling*. Add `nrlcom-casualty-ward` (`ENDPOINT="nrlcom-casualty-ward?competition=111"`) and `nrlcom-ladder` (`ENDPOINT="nrlcom-ladder?competition=111&season=$(date -u +%Y)"`) cases to the `case "$JOB"` block in `scripts/scout-refresh.sh`; sync the usage string + the file-header `# Usage:` line. Add two daily lines to `scripts/cron.d/jeromelu`: `30 18 * * * ubuntu /opt/jeromelu/scripts/scout-refresh.sh nrlcom-casualty-ward` and `45 18 * * * ubuntu /opt/jeromelu/scripts/scout-refresh.sh nrlcom-ladder` (off-peak, no collision with the 18:00/18:15 draw/match-centre slots). Do not touch the existing cases or the `--resolve`/`--max-time`/log-line machinery.
- **How to verify:** `bash -n scripts/scout-refresh.sh` → clean. Dry-run both jobs (e.g. echo the constructed `API_URL` for each) → `.../nrlcom-casualty-ward?competition=111` and `.../nrlcom-ladder?competition=111&season=<year>` as single quoted args (no unquoted `&` backgrounding). Both cron lines have 5 timing fields + `ubuntu` + the absolute script path; `grep -n "cron.d/jeromelu" scripts/lightsail-deploy.sh` confirms the install sync still covers the file. (First scheduled fire is operator/time-gated — deferred to TASK-27 closure, mirroring Phase 3 TASK-12.)
- **Proof notes:** _(empty at review time)_

### TASK-27 — prod seed + DB verification + docs (casualty/ladder closure)

- **What:** Per the plan's *Verification strategy (end-to-end)* + *Documentation updates*. On the prod box (loopback `--resolve api.jeromelu.ai:443:127.0.0.1`, `ADMIN_KEY` from `/opt/jeromelu/.env` per META): `POST /api/admin/scout/nrlcom-casualty-ward?competition=111` and `POST /api/admin/scout/nrlcom-ladder?competition=111&season=2026`; confirm `validated:true` + the S3 keys. Run extraction in the `jeromelu-api` container (Phase 3.5 `docker cp scripts → /runtmp` procedure; clean up `/runtmp` after): `--phase standings --seasons 2026` and `--phase injuries`. Then update docs: roadmap Phase 4 → ✅ Shipped (note extractor stays manual + the scheduled-extraction follow-up); charter Status cells + D4 (worker pending until TASK-28) + D13 inventory; both pipeline READMEs (DB extraction → live extractor + `## Tests` section + cadence); `scripts/data/populate/README.md` (injuries/standings now unit-tested); verify/refresh the `injuries` + `team_standings` data-docs-trinity entries. Create the run report `docs/build/runs/2026-05-28-scout-phase-4-casualty-ladder.md` + README row (this is the first task of the plan to be checked off → create the report now).
- **How to verify:** endpoints return `{ok:true, validated:true, s3_archive_key:...}` with `casualties>0` / `teams>0`; the S3 objects exist (`scout/nrlcom/casualty-ward/111/<YYYYMMDD>.json`, `scout/nrlcom/ladder/111/2026/round-NN.json`) and are independently reproducible. `SELECT count(*) FROM team_standings WHERE season=2026 AND competition=111` > 0 (≈17×rounds); `SELECT count(*) FROM injuries WHERE source='nrl.com/casualty-ward'` > 0; team_id resolution mostly non-null (spot-check). All listed docs updated and internally consistent (no "Deferred"/"not built" left for these two pipelines).
- **Proof notes:** _(empty at review time)_

### TASK-28 — retire worker-scraper (delete dir + doc sweep)

- **What:** Per the plan's *Files deleted* + *Documentation updates* (D4). Delete the entire `services/worker-scraper/` directory. Update the live docs that reference it: `docs/agents/system/scraper.md` (mark the Temporal worker **retired/deleted**), `docs/agents/crew/scout/charter.md` (D4 → done), `docs/agents/crew/scout/roadmap.md` (Phase 4 retirement line → done), `docs/agents/crew/scout/README.md`, `docs/agents/system/README.md`, `docs/architecture/08-technology-stack.md`, `docs/pages/wiki/data-feeds.md`. Leave `docs/archive/prd/jeromelu-ai-scraper-prd.md` (historical archive). Append the worker-scraper retirement to the Phase 4 run report.
- **How to verify:** `services/worker-scraper/` gone. `grep -rn "worker-scraper\|worker_scraper"` across the repo returns **only** `docs/archive/prd/` matches — zero code, compose (`docker/*.yml`), CI (`.github/`), deploy-script, or live-doc references. `make -n` unaffected; the api package still imports cleanly (nothing imported from the deleted dir — pre-verified at planning time). Confirmed orphaned at planning time: not present in either compose file, CI, or `Makefile`.
- **Proof notes:** _(empty at review time)_


## Completed work

Completed tasks are not kept here. When a task passes review and is checked off, what it delivered is recorded in the active run report under [`docs/build/runs/`](./runs/) and the task is removed from this file. This queue holds only open/in-flight work.
