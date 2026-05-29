# Jaromelu Task Queue

Persistent queue for the long-lived implementer session. The implementer reads top-down, completes one task at a time, dispatches `adversarial-reviewer` against the diff + task + plan, and only checks off after the review passes.

## Format

Each task is a level-3 heading with three labelled blocks (plus optional scheduling metadata, below):

- **What** — exactly what to do. References a section of `PLAN.md`.
- **How to verify** — concrete checks. Commands, files, expected output. Bar: "if satisfied exactly as written, the result is trustworthy."
- **Proof notes** — an optional in-flight scratchpad only. The **authoritative** proof record is the task's entry in the active run report under [`docs/build/runs/`](./runs/), written **at checkoff (after the review passes)**.

**Proof timing (important for reviewers):** under the run-report ritual, proof is recorded into the run report *at checkoff*, which is downstream of the review. So an **empty Proof-notes block at review time is expected and is NOT a blocker** — the reviewer verifies the diff against the spec and runs the **How to verify** checks itself; proof recording is a post-pass step.

Mark as `[x]` only after `adversarial-reviewer` passes. Once it passes, record what the task delivered in the active run report under [`docs/build/runs/`](./runs/) and **remove it from this file** — TASKS.md holds only the live queue, not a completed-task graveyard (see the run-report ritual in [META.md](./META.md)).

### Scheduling metadata (optional)

Two optional one-line fields at the **top** of a task, before **What**, let the implementer (and, later, a worktree dispatcher) decide ordering and safe concurrency. Both are written by the `planner`. Omit a field only when the answer is genuinely "none".

- **Depends-on.** Task IDs that must be checked off (and thus removed from the queue) before this task can start — e.g. `TASK-45`, or `none`. The implementer never picks a task whose dependencies are still open; it skips to the next eligible task rather than treating queue order alone as the gate.
- **Touches.** The repo paths/globs this task will create or modify — e.g. `services/api/app/scout/**`, `scripts/data/populate/phase_matches.py`. An operator-only task that changes no repo files declares `none`. **The concurrency contract:** two tasks may run at the same time only when their **Touches** sets are disjoint *and* neither **Depends-on** the other. For the single-implementer loop today this is documentation plus a smarter pick rule; it's the precondition a fan-out dispatcher relies on, so declare it honestly even while execution is serial.

### Tags

Prefix the title with optional tags in square brackets:

- `[P0]`, `[P1]`, `[P2]`, `[P3]` — severity (from `issue-triager`)
- `[BLOCKED: reason]` — implementer hit a wall; needs human input

---

## Open tasks

### TASK-45: Extractor sweep + DB conformance verification across full backfilled S3

**Depends-on.** none (TASK-37–39 extractor code already shipped). · **Touches.** none — operator task; runs extractors on the prod box and writes the DB + run-report scratchpad, no repo files.

**What.** Per [PLAN.md "Scout Phase 5"](./PLAN.md#2026-05-28-scout-phase-5--historical-backfill--standard-data-model-conformance) Tasks list + Verification §end-to-end. **Operator task** — run the (now era-aware) DB extractors across the full backfilled S3, then verify the canonical schema is populated end-to-end.

Steps (run on prod box, in the API container, same `docker cp scripts → /runtmp` pattern):

1. **Pre-flight**: confirm the prod API container has the TASK-37/38/39 code baked in:
   ```bash
   docker exec jeromelu-api python -c "from scripts.data.populate.phase_player_rounds import populate_player_rounds; print('ok')"
   docker exec jeromelu-api python -c "from scripts.data.populate.phase_matches import _extract_from_draw_fixture; print('ok')"
   ```
   Both must print `ok`. If not, deployment hasn't caught up — STOP and BLOCKED until [deploy pipeline path-filter](../../../../C:/Users/krist/.claude/projects/C--Users-krist-ClaudeProjects-Jeromelu/memory/project_deploy_pipeline_path_filter.md) resolves (push a forced-deploy trigger commit).

2. **Run each phase** with explicit wide season range:
   ```bash
   SEASONS=$(seq 1908 2026 | tr '\n' ' ')
   docker exec jeromelu-api python -m scripts.data.populate_db_from_s3 \
     --phase matches --seasons $SEASONS --competition 111 2>&1 | tee /runtmp/populate_matches.log

   docker exec jeromelu-api python -m scripts.data.populate_db_from_s3 \
     --phase team_lists --seasons $SEASONS --competition 111 2>&1 | tee /runtmp/populate_team_lists.log

   docker exec jeromelu-api python -m scripts.data.populate_db_from_s3 \
     --phase stats --seasons $SEASONS --competition 111 2>&1 | tee /runtmp/populate_stats.log

   docker exec jeromelu-api python -m scripts.data.populate_db_from_s3 \
     --phase timeline --seasons $SEASONS --competition 111 2>&1 | tee /runtmp/populate_timeline.log

   docker exec jeromelu-api python -m scripts.data.populate_db_from_s3 \
     --phase standings --competition 111 2>&1 | tee /runtmp/populate_standings.log

   docker exec jeromelu-api python -m scripts.data.populate_db_from_s3 \
     --phase leaderboards --competition 111 2>&1 | tee /runtmp/populate_leaderboards.log

   docker exec jeromelu-api python -m scripts.data.populate_db_from_s3 \
     --phase player_rounds --seasons $SEASONS --competition 111 2>&1 | tee /runtmp/populate_player_rounds.log
   ```

3. **Capture row counts + era distribution** via `psql`:
   ```sql
   SELECT data_coverage, COUNT(*) FROM matches WHERE competition_id=111 GROUP BY 1 ORDER BY 1;
   SELECT COUNT(*) FROM match_team_lists WHERE match_id IN (SELECT id FROM matches WHERE competition_id=111);
   SELECT COUNT(*) FROM player_match_stats WHERE match_id IN (SELECT id FROM matches WHERE competition_id=111);
   SELECT COUNT(*) FROM match_timeline WHERE match_id IN (SELECT id FROM matches WHERE competition_id=111);
   SELECT COUNT(*) FROM stat_leaderboards WHERE competition_id=111;
   SELECT COUNT(*) FROM team_standings WHERE competition_id=111;
   SELECT COUNT(*) FROM player_rounds WHERE season >= 2018;
   ```

4. **Spot-check queries** (each must return non-empty unless marked):
   - `SELECT season, round, status, data_coverage FROM matches WHERE season=1908 AND round=1 LIMIT 5` — non-empty, all `data_coverage='fixture_only'`.
   - `SELECT m.id, COUNT(t.*) AS tl_rows FROM matches m LEFT JOIN match_timeline t ON t.match_id=m.id WHERE m.season BETWEEN 1990 AND 1999 GROUP BY m.id ORDER BY tl_rows DESC LIMIT 5` — at least some matches with timeline rows + `data_coverage='timeline_only'`.
   - `SELECT COUNT(*) FROM player_match_stats WHERE match_id IN (SELECT id FROM matches WHERE season < 2000)` — **MUST be 0** (parent-coverage gate test).
   - `SELECT data_coverage FROM matches WHERE season=2026 ORDER BY id DESC LIMIT 5` — all `'full'` (regression check).
   - `SELECT season, COUNT(*) FROM player_rounds GROUP BY season ORDER BY season` — non-empty for 2018–2026.

5. **Idempotency check**: re-run one phase a second time — log shows `inserted=0` and `updated=N` matching the first run's total.

**How to verify.**
- Each phase log exits 0 with a summary report at the bottom (`done. summary: {...}`).
- Row counts meet PLAN.md's thresholds: `matches.full ≥4500`, `matches.timeline_only ≥800`, `matches.fixture_only ≥2000`; `stat_leaderboards ≥4500`; `team_standings ≥600`; `player_rounds (2018+) ≥150000`.
- All 5 spot-check queries return as specified (including the one that MUST return 0).
- Re-run shows `inserted=0`.
- All counts + spot-check outputs copied verbatim into the run report scratchpad on this task's checkoff.

**Proof notes.**

---

### TASK-46: Phase 5 closure — docs sweep + run report → Shipped

**Depends-on.** TASK-45 (its row counts + spot-check outputs feed these docs). · **Touches.** `docs/agents/crew/scout/**`, `docs/operations/data-lineage/matches.md`, `services/api/app/scout/{nrlcom_draw,nrlcom_match_centre,nrlcom_ladder,nrlcom_stats,supercoach_stats}/README.md`, `scripts/data/populate/README.md`, `docs/build/runs/**`, `docs/build/PLAN.md`, `docs/build/TASKS.md`.

**What.** Per [PLAN.md "Scout Phase 5"](./PLAN.md#2026-05-28-scout-phase-5--historical-backfill--standard-data-model-conformance) Documentation updates §.

Files to update:

1. `docs/agents/crew/scout/roadmap.md`:
   - Phase 5 heading: `### Phase 5 — Historical backfill (one-time, ~5-6 hours operationally) ✅ Shipped (YYYY-MM-DD)`
   - Body: replace the In-design checklist with the actual row counts achieved (per TASK-45 verification), the `data_coverage` distribution table, and a "Deferred (out of scope, surfaced not self-queued)" list (e.g., casualty-ward historical — no upstream support per D12; nrl.com per-team roster historical — same).

2. `docs/agents/crew/scout/charter.md`:
   - D12 row-counts column: update to actuals.
   - Add a "Standard data model — era reconciliation" sub-section under D12 documenting the `matches.data_coverage` decision and the "NULLs + era marker, never alternate tables" principle (cite this plan).

3. `docs/operations/data-lineage/matches.md`:
   - Document the new `data_coverage` column + its CHECK constraint.
   - Era-banded row count breakdown table (one row per coverage value with count + season range).
   - 4 spot-check queries from TASK-45 listed for operator reference.

4. 5 pipeline READMEs (`services/api/app/scout/{nrlcom_draw,nrlcom_match_centre,nrlcom_ladder,nrlcom_stats,supercoach_stats}/README.md`):
   - "Archive-only mode" section: when to use (`archive_only=true` for historical backfill); the response shape (`validated:false, validation_skipped:true`); default behaviour unchanged (daily cron leaves it false).
   - For `nrlcom_match_centre/README.md` specifically: document the 1990–1999 partial-shape expectation and how it surfaces as `data_coverage='timeline_only'` in the matches table.

5. `scripts/data/populate/README.md`:
   - New row in the phase table: `player_rounds` reads `nrlsupercoachstats/stats/*`, writes `player_rounds` (UPSERT on `(player_id, round, season)`), wired via `--phase player_rounds`.

6. `docs/build/runs/2026-05-28-scout-phase-5-historical-backfill.md`:
   - Status: `🟢 Shipped`.
   - Per-task entries with what each delivered (files, proof, commit SHA).
   - Decisions & deviations.
   - Outstanding deferred items.
   - Lessons learned.
   - Commits list.

7. `docs/build/runs/README.md`:
   - Add the new row (newest first).

8. `docs/build/PLAN.md`:
   - Remove the Phase 5 plan from "Active plan" — leave the "Last shipped initiative" pointer updated to this run.

**How to verify.**
- `git diff --stat` covers the 11+ doc files listed above and NO code files.
- `grep -r "Phase 5" docs/agents/crew/scout/roadmap.md docs/agents/crew/scout/charter.md` — every reference reflects ✅ Shipped.
- `docs/build/PLAN.md` "Active plan" section is empty (or shows the next-up plan if one's been started).
- `docs/build/TASKS.md` "Open tasks" section is empty (all Phase 5 tasks removed per the META ritual).
- `docs/build/runs/README.md` top row is the Phase 5 entry.
- The run report's per-task entries match the commit SHAs in `git log --oneline -20` (TASK-37 through TASK-46).
- All TASK-37..TASK-46 entries also removed from TASKS.md (each task's checkoff already did this; verify the file ends with `## Open tasks` empty + `## Completed work` blurb only).

**Proof notes.**

---


## Completed work

Completed tasks are not kept here. When a task passes review and is checked off, what it delivered is recorded in the active run report under [`docs/build/runs/`](./runs/) and the task is removed from this file. This queue holds only open/in-flight work.
