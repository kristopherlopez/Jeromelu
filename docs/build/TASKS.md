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

### TASK-34 — extractor unit tests for `populate_stat_leaderboards` via pure-function refactor

**What**

Behaviour-preserving refactor of `scripts/data/populate/phase_aux.py:populate_stat_leaderboards` to expose a pure projection seam — mirrors Phase 4 TASK-25's treatment of ladder + casualty. See `PLAN.md` → `## 2026-05-28: Scout Phase 4.5` → Interface → *nrlcom-stats* (last bullet).

1. Modify `scripts/data/populate/phase_aux.py`:
    - Extract `_extract_leader_rows(payload: dict, *, key: str, competition: int, season: int, team_map: dict[str, str], player_map: dict[int, str]) -> list[dict[str, Any]]` — pure function that walks `playerStats[]` and `teamStats[]` and returns the list of row-dicts the current inline code builds. No DB, no I/O. The float-coercion of `leader_value`, the team_nickname lookup via `team_map`, and the `playerId → person_id` lookup via `player_map` (only for `scope='player'`) all stay inside the pure function. `raw_payload` value (`json.dumps(leader, default=str)`) stays inside the pure function.
    - In `populate_stat_leaderboards`, replace the nested `for scope_key …: for category_block …: for subgroup_block …: for pos_idx, leader …:` block with: per-archive, call `_extract_leader_rows(payload, key=key, competition=competition, season=season, team_map=team_map, player_map=player_map)` and loop `for row in rows: res = db.execute(upsert_sql, row); if res.scalar(): inserted += 1; else: updated += 1`.
    - **Behaviour must be byte-equivalent** — same UPSERT SQL string, same counters, same `commit` guard, same logging.
2. Create `tests/unit/scripts/data/populate/test_phase_leaderboards.py`:
    - Load the TASK-29 canonical fixture (`tests/fixtures/scout/nrlcom_stats/canonical_response.json`) via the same `fixtures_dir` fixture the casualty/ladder unit tests use.
    - 5+ tests over `_extract_leader_rows`:
      - **`test_one_player_leader_projection`** — pass a minimal payload (one `playerStats[0].groups[0].leaders[0]` only) with known `firstName/lastName/teamNickName/value/playerId`; assert the returned row's exact field-by-field mapping (every column of `stat_leaderboards` named).
      - **`test_player_scope_resolves_person_id_when_player_id_present`** — `player_map={123: "uuid-aaa"}`, leader has `playerId=123`; assert row's `person_id == "uuid-aaa"`. Then the same leader with `playerId=None` → `person_id is None`.
      - **`test_team_scope_always_emits_person_id_none`** — payload with one `teamStats[0]…leaders[0]`; assert `row["scope"] == "team"` and `row["person_id"] is None` regardless of `player_map` contents.
      - **`test_leader_value_float_coercion`** — `leader["value"] = "12.5"` → row `leader_value == 12.5`; `leader["value"] = ""` → `None`; `leader["value"] = None` → `None`; `leader["value"] = "abc"` → `None`.
      - **`test_team_nickname_lookup`** — `team_map={"storm": "uuid-team-storm"}`, leader `teamNickName="Storm"` → `team_id == "uuid-team-storm"`. Unknown nickname → `team_id is None`. Fallback `teamName` when `teamNickName` missing (per the existing extractor logic: `nick = leader.get("teamNickName") or leader.get("teamName") or ""`).
      - **`test_canonical_fixture_round_trip`** — load the real fixture, call `_extract_leader_rows(fixture, key="scout/nrlcom/stats/111/2026.json", competition=111, season=2026, team_map={}, player_map={})`; assert `len(rows) >= number_of_subgroups`, every row has the 17 required keys (column set), `s3_archive_key == "scout/nrlcom/stats/111/2026.json"` everywhere, and each row's `leader_position` is ≥1.

**How to verify**

- `pytest tests/unit/scripts/data/populate/test_phase_leaderboards.py -v` → 6 passed.
- `pytest tests/unit/scripts/data/populate/test_dry_run_flag.py -v` → 12 passed (the TASK-18 commit-guard contract still holds — `commit: bool = True` still threaded through `populate_stat_leaderboards`).
- `pytest tests/unit/scripts/data/populate/` → all green.
- `python -c "from scripts.data.populate.phase_aux import _extract_leader_rows, populate_stat_leaderboards; print('ok')"` → `ok`.
- `python -m scripts.data.populate_db_from_s3 --help` → exits 0 (the orchestrator imports the refactored function).
- `pytest tests/unit/` → no regression vs. TASK-33 baseline.
- Manual byte-equivalence check (no test): `git diff HEAD~ scripts/data/populate/phase_aux.py` — only the refactor seam diff; the SQL string, counters, commit guard, logging unchanged.

**Proof notes**

_(in-flight scratchpad)_

---

### TASK-35 — schedule cron for nrlcom-stats (daily 18:50 UTC) + nrlcom-players-roster (weekly Tue 23:40 UTC)

**What**

Cron scheduling. See `PLAN.md` → `## 2026-05-28: Scout Phase 4.5` → Interface → *Cron*.

1. Modify `scripts/scout-refresh.sh`:
    - Add two `case` entries to the existing `case "$JOB" in` block:
      - `nrlcom-stats) ENDPOINT="nrlcom-stats?competition=111&season=$(date -u +%Y)" ;;`
      - `nrlcom-players-roster) ENDPOINT="nrlcom-players-roster/refresh-all?competition=111" ;;`
    - Update the `# Usage:` header line to list the two new jobs in the same order.
    - Update the `*)` catch-all error string identically.
2. Modify `scripts/cron.d/jeromelu`:
    - Add (positioned at the end of the existing 18:xx UTC nrl.com block, right after the `45 18` ladder line):
      ```
      # Daily nrl.com stats snapshot — 18:50 UTC = 04:50 AEST. Pre-computed top-25
      # leaderboards (~275KB) for NRL (111), current season. Archives
      # scout/nrlcom/stats/111/{season}.json. Cheap to run daily even though
      # the leaderboards only change a few times per week.
      50 18 * * *     ubuntu  /opt/jeromelu/scripts/scout-refresh.sh nrlcom-stats
      ```
    - Add (positioned at the end of the existing Mon 23:xx UTC weekly block, right after the `35 23 * * 1` supercoach-settings line):
      ```
      # Weekly nrl.com players roster — Mondays 23:40 UTC = Tuesday 09:40 AEST.
      # Walks the 17 NRL teams via refresh-all (1 req/sec; ~20s wall time).
      # Profile data (DOB, position, image) changes slowly; weekly is right.
      40 23 * * 1     ubuntu  /opt/jeromelu/scripts/scout-refresh.sh nrlcom-players-roster
      ```

**How to verify**

- `bash -n scripts/scout-refresh.sh` → clean (syntax-only check, no execution).
- Case simulation in a one-liner:
  ```bash
  for j in nrlcom-stats nrlcom-players-roster; do JOB=$j; case "$JOB" in nrlcom-stats) ENDPOINT="nrlcom-stats?competition=111&season=$(date -u +%Y)" ;; nrlcom-players-roster) ENDPOINT="nrlcom-players-roster/refresh-all?competition=111" ;; esac; echo "$j → $ENDPOINT"; done
  ```
  → emits `nrlcom-stats → nrlcom-stats?competition=111&season=2026` (or current year) and `nrlcom-players-roster → nrlcom-players-roster/refresh-all?competition=111`. The `&` stays inside the double-quoted `ENDPOINT` (the entire URL is passed via `curl -X POST "$API_URL"` so no shell backgrounding).
- Both new cron lines: 5 timing fields + `ubuntu` + absolute path; no collision with existing slots (18:00/18:15/18:30/18:45 NRL.com block; Mon 23:00/23:15/23:30/23:35 weekly block; 16:30 pg-backup; 00:30 cron-report; 22:00/22:30 Mon content/disk).
- `grep -n "cron.d/jeromelu" scripts/lightsail-deploy.sh` → the install/sync step still references the file (and so the new lines reach the box on the next deploy pull).
- Cron-line correctness: `grep -E '^[0-9]+ [0-9]+ \* \* (\*|[0-9]+)' scripts/cron.d/jeromelu | wc -l` → previous count + 2.
- **First scheduled fire is operator/time-gated** — defer the actual `/var/log/jeromelu/scout-refresh.log` confirmation to TASK-36 closure (mirrors Phase 4 TASK-26 deferral pattern). The TASK-36 seed exercises the endpoints end-to-end; this task only ships the scheduling.

**Proof notes**

_(in-flight scratchpad)_

---

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
