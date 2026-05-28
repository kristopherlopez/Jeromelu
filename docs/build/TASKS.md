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

### TASK-42: Operator backfill — `nrlcom-match-centre` 1990–2026 (on prod box via loopback)

**What.** Per [PLAN.md "Scout Phase 5"](./PLAN.md#2026-05-28-scout-phase-5--historical-backfill--standard-data-model-conformance) Tasks list. **Operator task** — same procedure as TASK-41.

Key differences from TASK-41:
- **Wall-clock**: ~5500 GETs at 1 req/sec ≈ **3–4h**. Use `tmux`/`screen` mandatory.
- **Seasons**: 1990–2026 (pre-1990 has no match-centre URL in the draw fixtures per D12; the walker auto-skips fixtures missing `matchCentreUrl`).
- **Round depth**: `--round-from 1 --round-to 30` (the walker discovers fixtures from the draw; per-round wall-clock varies).
- **Resume granularity**: round-level (per the TASK-40 design — list `scout/nrlcom/match-centre/{comp}/{season}/round-{NN}/` prefix; skip if any keys exist).

Run command (replace the source param in TASK-41's invocation):
```bash
docker exec -it jeromelu-api bash -c "
  cd /runtmp && python -m scripts.data.scout_backfill \
    --source nrlcom-match-centre \
    --season-from 1990 --season-to 2026 \
    --round-from 1 --round-to 30 \
    --competition 111 \
    --api https://api.jeromelu.ai \
    --admin-key \$ADMIN_KEY \
    --archive-only --resume \
    --rate-limit 1.0 2>&1 | tee /runtmp/backfill_nrlcom-match-centre_$(date +%Y%m%d_%H%M).log
"
```

**How to verify.**
- `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/match-centre/111/ --recursive | wc -l` ≥ **4500** (post-2000 has ~200 matches/year × 26 years; pre-2000 mostly empty payloads).
- `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/match-centre/111/ --recursive | awk -F/ '{print $5}' | sort -u | wc -l` ≥ **30** (distinct season folders).
- Pre-2000 spot-check: `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/match-centre/111/1995/ --recursive` returns either a small set of keys (pre-2000 has thin payloads, mostly timeline) OR zero (if 1995 draws had no `matchCentreUrl`). Both acceptable; record actual count.
- Post-2000 spot-check: `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/match-centre/111/2010/ --recursive | wc -l` ≥ 180.
- One specific S3 inspect: `aws s3 cp $(aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/match-centre/111/2010/ --recursive | head -1 | awk '{print "s3://jeromelu-clean-documents/" $4}') - | jq 'keys | length'` returns a reasonable key count (≥4 — `players`/`stats`/`timeline`/`match` for full-shape post-2010).
- Driver final summary (successes / failures / first 20 failure lines) recorded in run report scratchpad.

**Proof notes.**

---

### TASK-43: Operator backfill — short bundle (ladder 1996–2026, stats 2013–2026, SC siblings 2024–2025)

**What.** Per [PLAN.md "Scout Phase 5"](./PLAN.md#2026-05-28-scout-phase-5--historical-backfill--standard-data-model-conformance) Tasks list. **Operator task** — three small backfills bundled because each is fast (under 15 min combined) and the verification cadence is identical.

Three sequential invocations on the prod box (no tmux needed; total wall-clock <20 min):

```bash
# 1. nrl.com ladder — 30 seasons × ~24 rounds avg = ~720 GETs at 1 req/sec ≈ 12 min
docker exec -it jeromelu-api bash -c "
  cd /runtmp && python -m scripts.data.scout_backfill \
    --source nrlcom-ladder --season-from 1996 --season-to 2026 \
    --round-from 1 --round-to 30 --competition 111 \
    --api https://api.jeromelu.ai --admin-key \$ADMIN_KEY \
    --archive-only --resume --rate-limit 1.0 2>&1 | tee /runtmp/backfill_nrlcom-ladder_$(date +%Y%m%d_%H%M).log
"

# 2. nrl.com stats — 14 seasons × 1 endpoint = 14 GETs ≈ 30 sec
docker exec -it jeromelu-api bash -c "
  cd /runtmp && python -m scripts.data.scout_backfill \
    --source nrlcom-stats --season-from 2013 --season-to 2026 \
    --competition 111 \
    --api https://api.jeromelu.ai --admin-key \$ADMIN_KEY \
    --archive-only --resume --rate-limit 1.0 2>&1 | tee /runtmp/backfill_nrlcom-stats_$(date +%Y%m%d_%H%M).log
"

# 3. SC siblings — supercoach-roster + supercoach-teams + supercoach-settings for 2024 and 2025
for src in supercoach-roster supercoach-teams supercoach-settings; do
  docker exec -it jeromelu-api bash -c "
    cd /runtmp && python -m scripts.data.scout_backfill \
      --source $src --season-from 2024 --season-to 2025 \
      --api https://api.jeromelu.ai --admin-key \$ADMIN_KEY \
      --rate-limit 1.0 2>&1 | tee /runtmp/backfill_${src}_$(date +%Y%m%d_%H%M).log
  "
done
```

(SC siblings run WITHOUT `--archive-only` because the 2-season window is modern-shape per D12; `--resume` is a no-op for them per the TASK-40 design.)

**How to verify.**
- `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/ladder/111/ --recursive | wc -l` ≥ **600**.
- `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/stats/111/ --recursive | wc -l` = **14** (2013–2026 inclusive).
- `aws s3 ls s3://jeromelu-clean-documents/scout/supercoach/classic/players-cf/ --recursive | wc -l` ≥ **2** (2024 + 2025; daily timestamps may produce more if existing 2025 data was already there).
- `aws s3 ls s3://jeromelu-clean-documents/scout/supercoach/classic/teams/ --recursive | wc -l` ≥ **2** (2024 + 2025 — the existing seed was 2026 only).
- `aws s3 ls s3://jeromelu-clean-documents/scout/supercoach/classic/settings/ --recursive | wc -l` ≥ **2**.
- Each driver invocation reports successes / failures in its final summary — record in run report scratchpad.
- SC siblings: backfilling DOES write to DB (no archive_only flag) — verify `SELECT COUNT(*) FROM sc_settings WHERE season IN (2024, 2025)` ≥ 2 (one per mode × season at minimum).

**Proof notes.**

---

### TASK-45: Extractor sweep + DB conformance verification across full backfilled S3

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
