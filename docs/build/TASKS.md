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

### TASK-36 — prod seed + DB verification + docs (Phase 4.5 closure)

**What**

Phase 4.5 closure. See `PLAN.md` → `## 2026-05-28: Scout Phase 4.5` → Interface → *Seed + DB verification* and → *Documentation updates*. Mirrors Phase 4 TASK-27 line-for-line.

1. **Seed prod via loopback** (`--resolve api.jeromelu.ai:443:127.0.0.1` from the box; `ADMIN_KEY` from `/opt/jeromelu/.env`):
    - `curl -s -X POST "https://api.jeromelu.ai/api/admin/scout/nrlcom-stats?competition=111&season=2026" --resolve api.jeromelu.ai:443:127.0.0.1 -H "X-Admin-Key: $ADMIN_KEY" | python -m json.tool` → response shows `ok:true`, `validated:true`, `s3_archive_key:"scout/nrlcom/stats/111/2026.json"`, `player_stat_groups > 0`, `team_stat_groups > 0`. Verify S3: `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/stats/111/` → `2026.json` recent stamp, ~275KB.
    - `curl -s -X POST "https://api.jeromelu.ai/api/admin/scout/nrlcom-players-roster/refresh-all?competition=111" --resolve api.jeromelu.ai:443:127.0.0.1 -H "X-Admin-Key: $ADMIN_KEY" -m 120 | python -m json.tool` → `teams_walked: 17`, `errors: []`, each `results[i].validated == true`. Verify S3: `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/players-roster/111/` → 17 `team-{team_id}.json` keys present, recent stamps.
2. **Container-side populate** (Phase 3.5 `docker cp scripts → /runtmp` procedure documented in `scripts/data/populate/README.md`):
    - `docker exec jeromelu-postgres psql -U jeromelu_admin -d jeromelu -c "SELECT COUNT(*) FROM stat_leaderboards WHERE season=2026 AND competition=111;"` — pre-seed count.
    - `docker cp scripts jeromelu-api:/runtmp/scripts` (per the existing procedure); `docker exec jeromelu-api bash -lc "cd /runtmp && python -m scripts.data.populate_db_from_s3 --phase leaderboards --competition 111"` → logs show `phase_leaderboards: inserted=N updated=M`; `--phase` runs cleanly without the Phase-4 `jsonb_build_object` class of latent bug surfacing (none expected — the UPSERT here uses simple bound params throughout).
    - Cleanup: `docker exec jeromelu-api rm -rf /runtmp` after.
3. **Post-seed DB verification** (read-only via `docker exec jeromelu-postgres psql`):
    - `SELECT COUNT(*) FROM stat_leaderboards WHERE season=2026 AND competition=111;` → returns the seeded count.
    - `SELECT COUNT(*) FILTER (WHERE person_id IS NOT NULL) * 100.0 / COUNT(*) FROM stat_leaderboards WHERE scope='player' AND season=2026 AND competition=111;` → ≥80% (the Phase 4 ladder bar). Below 70% is a yellow flag worth a Concern in the run report.
    - `SELECT COUNT(*) FILTER (WHERE team_id IS NOT NULL) * 100.0 / COUNT(*) FROM stat_leaderboards WHERE season=2026 AND competition=111;` → ≥90% (the team-nickname lookup map should be near-complete).
    - Spot-check: `SELECT category, subgroup, leader_first_name, leader_last_name, leader_team_nickname, leader_value FROM stat_leaderboards WHERE season=2026 AND competition=111 AND scope='player' AND leader_position=1 ORDER BY category, subgroup LIMIT 10;` — the leaders should match `https://www.nrl.com/stats/?competition=111&season=2026` page for at least the well-known categories (Total Points / Tries / Tackles).
4. **Documentation updates** — apply every entry under `PLAN.md` → `## 2026-05-28: Scout Phase 4.5` → *Documentation updates*. The new run report at `docs/build/runs/2026-05-28-scout-phase-4-5-stats-players-roster.md` should already exist (created when TASK-29 closed); set its status to **🟢 Shipped** in this task and record what each task delivered (files, proof, commit SHA) per `META.md` ritual. Remove the Phase 4.5 plan section from `PLAN.md`'s `## Active plan` once the run report is finalised.
5. **Box-side reverts:** if any in-place edits were made on the box during seed (e.g. file overrides), revert them via `git checkout` so the next prod pull stays clean (mirrors Phase 4 TASK-27 closing step).

**How to verify**

- Endpoint responses include the expected fields (above) and S3 archives land at the expected keys with reasonable sizes/timestamps.
- `stat_leaderboards` row count grows by the expected per-season cardinality (~25 leaders × number of subgroups across `playerStats`+`teamStats`).
- person_id / team_id resolution percentages meet the bars above; if not, document the gap explicitly in the run report with a follow-up (do not silently move on).
- All docs in the plan's *Documentation updates* list show their post-seed numbers / shipped flips.
- `git status` after the task is clean: only TASKS.md removal of TASK-36, PLAN.md removal of the Phase 4.5 section, and the run report finalisation. No stray edits.
- Outstanding/deferred items recorded explicitly in the run report's *Outstanding* section: at minimum (a) **cron first-fire** (operator/time-gated, mirror of Phase 4 TASK-26 deferral), (b) **extractor scheduling** (the cross-cutting Phase 4 follow-up — daily ingest cron archives to S3 but DB only refreshes when an operator runs `populate_db_from_s3 --phase leaderboards`; the `nrlcom_players_roster` pipeline has the same gap doubled because no extractor at all exists this phase).

**Proof notes**

_(in-flight scratchpad)_


## Completed work

Completed tasks are not kept here. When a task passes review and is checked off, what it delivered is recorded in the active run report under [`docs/build/runs/`](./runs/) and the task is removed from this file. This queue holds only open/in-flight work.
