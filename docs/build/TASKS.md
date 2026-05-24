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

### [BLOCKED: awaiting first cron fire — verify scout-refresh.log on/after 2026-05-25 23:35 UTC] TASK-06: One-time S3 seed + DB verification + roadmap/charter status flip + S3 profile docs refresh

Implements PLAN.md § 2026-05-24 Phase 2.5 closure / "One-time S3 seed run" + "Documentation updates". This is the closure task — only run after TASK-01 through TASK-05 are merged and the cron is deployed.

> **Steps 1–7 DONE 2026-05-24** (commit `8ed6e37`, adversarial-reviewer PASS WITH CONCERNS — both non-blocking). The ADMIN_KEY gate was resolved by the operator authorising key retrieval; the seed ran on the prod box. **Only the final verification bullet remains** and cannot be observed yet:
> - The recurring cron fires **Mon 2026-05-25 23:30 UTC** (teams) / **23:35 UTC** (settings). To close: confirm `/var/log/jeromelu/scout-refresh.log` shows both `supercoach-teams` and `supercoach-settings` jobs ran clean (status=2xx), or that the Tuesday cron-health email reports them green. Then mark `[x]` and move to Completed.
> - Box state confirmed during seed: git HEAD `b031fff`, `/etc/cron.d/jeromelu` already carries the two SC lines, SC make targets present — so the cron deploy precondition is already met.

**Proof notes (steps 1–7, 2026-05-24)**
- **Seed (prod box via SSH, curl with `--resolve api.jeromelu.ai:443:127.0.0.1`; ADMIN_KEY from `/opt/jeromelu/.env`, never printed):**
  - teams: `{"ok": true, "season": 2026, "fetched": 17, "matched": 17, "unknown_abbrev": [], "missing_team_row": []}`
  - settings classic: `{"ok": true, "mode": "classic", "upserted_id": "8cb12dca-c65d-4c92-a740-0caf924d6981"}`
  - settings draft: `{"ok": true, "mode": "draft", "upserted_id": "f48996b6-9f4e-452b-83ce-4ef78a0142f9"}`
  - Note: responses carry `matched`/`upserted_id`, **not** `s3_archive_key` (spec expectation didn't match the route's actual return shape — `s3_archive_key` is recorded in the audit detail + `sc_settings`, not the HTTP body). Reviewer confirmed via `routes.py` this is correct; direct `aws s3 ls` used as authoritative S3 proof.
- **S3 (`aws s3 ls`, ap-southeast-2; reviewer independently reproduced):** `classic/teams/2026.json` (3176 B), `classic/settings/2026/20260524.json` (16994 B), `draft/settings/2026/20260524.json` (15760 B) — all dated 2026-05-24.
- **DB (box, `docker exec jeromelu-postgres psql -U jeromelu_admin -d jeromelu`):** `sc_settings` → 2 rows season 2026 captured_date 2026-05-24 (classic 16994 B, draft 15760 B). `teams` → 17 rows with `metadata_json ? 'supercoach'`, all distinct abbrevs.
- **Docs (commit `8ed6e37`):** regenerated `classic-settings.md` (2→3 samples) + `draft-settings.md` (1→2 samples); `classic-teams.md` no diff (byte-identical overwrite). Flipped roadmap Phase 2.5 heading + bullets to Shipped; flipped charter `supercoach_teams/` + `supercoach_settings/` Status to `✅ shipped (Phase 2.5)`. Added `## Tests` sections to both pipeline READMEs.

**What**
1. **Trigger the seed against prod yourself.** `ADMIN_KEY` must be available in your environment — on Lightsail it lives at `/opt/jeromelu/.env`; locally, source it from the same place the operator's shell would (e.g. a `.env` you load before starting the session). If `ADMIN_KEY` is not set, tag this task `[BLOCKED: ADMIN_KEY not available in implementer environment]` and pick the next task — do not improvise.
   ```bash
   make scout-supercoach-teams ADMIN_KEY=$ADMIN_KEY SEASON=2026 API=https://api.jeromelu.ai
   make scout-supercoach-settings ADMIN_KEY=$ADMIN_KEY SEASON=2026 MODE=classic API=https://api.jeromelu.ai
   make scout-supercoach-settings ADMIN_KEY=$ADMIN_KEY SEASON=2026 MODE=draft    API=https://api.jeromelu.ai
   ```
   Capture each response (the curl pipes to `json.tool`) into proof notes — each should include `"ok": true` and an `s3_archive_key` value.
2. **Verify S3 lands the artefacts:**
   ```bash
   aws s3 ls s3://jeromelu-clean-documents/scout/supercoach/classic/teams/   # expect 2026.json with today's mtime
   aws s3 ls s3://jeromelu-clean-documents/scout/supercoach/classic/settings/2026/  # expect <YYYYMMDD>.json dated today
   aws s3 ls s3://jeromelu-clean-documents/scout/supercoach/draft/settings/2026/    # expect <YYYYMMDD>.json dated today
   ```
3. **Verify DB rows** via `make db-shell` (or directly: `docker compose -f docker/docker-compose.yml exec postgres psql -U $POSTGRES_USER $POSTGRES_DB`):
   ```sql
   SELECT season, captured_date, mode, length(payload::text) AS payload_bytes
     FROM sc_settings ORDER BY captured_at DESC LIMIT 5;
   -- Expect two rows for season=2026 dated today: one mode='classic', one mode='draft'.

   SELECT slug, metadata_json->'supercoach'->>'abbrev' AS sc_abbrev
     FROM teams
     WHERE metadata_json ? 'supercoach'
     ORDER BY slug;
   -- Expect 17 rows, one per NRL club. Capture the full output to proof notes.
   ```
4. **Refresh the S3 profile docs** (these are generated, not hand-written): run `python scripts/profile_s3_json.py` (or whichever invocation the script documents) for the three SC paths affected. Files to regenerate:
   - `docs/operations/data-sources/supercoach/classic-teams.md`
   - `docs/operations/data-sources/supercoach/classic-settings.md`
   - `docs/operations/data-sources/supercoach/draft-settings.md`
   Commit only the diffs that reflect today's seed (sample-count line goes from 1/2 → 2/3 etc.).
5. **Flip the roadmap status** in `docs/agents/crew/scout/roadmap.md`:
   - Line 58 heading: change `Phase 2.5 — Bronze (S3-first) retrofit ✅ + lightweight SC siblings (In design)` to `Phase 2.5 — Bronze (S3-first) retrofit ✅ + lightweight SC siblings ✅ Shipped`.
   - Lines 60–64: rewrite the bullets to past-tense Shipped status, e.g. `- ✅ Shipped: scout/supercoach_teams/ — weekly cron, S3 archive at scout/supercoach/classic/teams/, cross-references teams.metadata_json.supercoach.` Mirror the existing Phase-1 / Phase-2 "loose end" prose style.
6. **Flip the charter status** in `docs/agents/crew/scout/charter.md` table around lines 42–43:
   - `scout/supercoach_teams/` Status column: `🟡 not built — Phase 2.5` → `✅ shipped (Phase 2.5)`
   - `scout/supercoach_settings/` Status column: `🟡 not built` → `✅ shipped (Phase 2.5)`
7. **Add Tests sections to the per-pipeline READMEs:**
   - `services/api/app/scout/supercoach_teams/README.md`: append `## Tests` section listing `tests/unit/api/scout/test_supercoach_teams_models.py` (always-on) and `tests/integration/scout/test_supercoach_teams_response_shape.py` (env-flagged with `SCOUT_DRIFT_LIVE=1`).
   - `services/api/app/scout/supercoach_settings/README.md`: same shape, and note the integration test parameterises over `classic` and `draft` modes.

**How to verify**
- Three `make` commands each return JSON with `"ok": true` and a non-null `s3_archive_key`. Paste into proof notes.
- Three `aws s3 ls` commands each show today-dated keys.
- `sc_settings` query returns exactly two rows dated today (one classic, one draft). The `teams` query returns 17 distinct rows with non-null `sc_abbrev`.
- After the documentation edits, `git diff docs/agents/crew/scout/roadmap.md docs/agents/crew/scout/charter.md services/api/app/scout/supercoach_teams/README.md services/api/app/scout/supercoach_settings/README.md docs/operations/data-sources/supercoach/` shows only status-flip and profile-refresh changes — no unrelated edits.
- The next-Tuesday-after-deploy cron-health email (or `cat /var/log/jeromelu/scout-refresh.log | grep supercoach`) shows both jobs ran clean. Capture that log line in proof notes once observed.

**Proof notes**
_(implementer fills in: three curl responses, three aws s3 ls outputs, two SQL query results, doc diff summary, first-cron-fire log line)_


### TASK-14: Unit tests for `phase_matches._extract_one` (no refactor needed)

Implements PLAN.md § 2026-05-24 Scout Phase 3.5 / Interface / pure extract (matches). Depends on TASK-13.

**What**
1. Create `tests/unit/scripts/data/populate/test_phase_matches.py`. Import `_extract_one`, `_normalize_status`, `_KEY_RE`, `_GRADE_MAP` from `scripts.data.populate.phase_matches`. Use the `fixtures_dir` conftest fixture; load `fixtures_dir / "scout" / "nrlcom_match_centre" / "canonical_response.json"` (the Phase 3 FullTime fixture). Build fake maps: `team_map = {<homeTeam.teamId>: "11111111-1111-1111-1111-111111111111", <awayTeam.teamId>: "22222222-..."}` (read the two teamIds from the fixture), `venue_map = {}`.
2. Tests:
   - `test_extract_one_maps_core_fields` — `_extract_one(payload, "scout/nrlcom/match-centre/111/2026/round-12/raiders-v-dolphins.json", team_map, venue_map)` returns a dict with `source=="nrl_com"`, `external_match_id == payload["matchId"]`, `season==2026`, `round==12`, `grade=="nrl"`, `status=="final"` (FullTime), `home_team_id`/`away_team_id` resolved from the map, and `referee_name` is the referee from `officials[]`.
   - `test_attendance_zero_becomes_null` — set `payload["attendance"]=0` (deepcopy) → returned `attendance` is `None`.
   - `test_unresolved_team_returns_none` — `team_map={}` → returns `None` (skip-no-team).
   - `test_same_team_returns_none` — map both teamIds to the same id → returns `None` (distinct-teams guard).
   - `test_key_regex_and_status_map` — `_KEY_RE` parses comp/season/round/slug from a sample key; `_normalize_status("FullTime")=="final"`, `_normalize_status("Upcoming")=="scheduled"`, `_normalize_status(None)=="scheduled"`; `_GRADE_MAP[111]=="nrl"`.

**How to verify**
- `pytest tests/unit/scripts/data/populate/test_phase_matches.py -v` — all pass.
- `pytest tests/unit/ -q` stays green. `git status` shows one new test file.

**Proof notes**
_(implementer fills in)_


### TASK-15: Refactor `phase_stats` to a pure `_extract_stat_rows` + unit tests

Implements PLAN.md § 2026-05-24 Scout Phase 3.5 / Interface / pure extract (stats). Depends on TASK-13.

**What**
1. **Behavior-preserving refactor** of `scripts/data/populate/phase_stats.py`: extract the inlined per-player row-building (currently inside the `for side_key ... for s in stats_block` loop in `populate_player_match_stats`) into a pure module-level function `_extract_stat_rows(payload, key, match_id, team_map, player_map) -> list[dict]`. It must return the same `row` dicts the loop currently builds (match_id, nrlcom_match_id, nrlcom_player_id, person_id, team_id, nrlcom_team_id, is_home, jersey_number, position, is_on_field, all `_FIELD_MAP` columns, raw_payload, s3_archive_key). `populate_player_match_stats` then calls `_extract_stat_rows(...)` and only does the UPSERT loop over the returned rows. No change to the UPSERT SQL, the maps, or the return summary.
2. Create `tests/unit/scripts/data/populate/test_phase_stats.py`. Import `_extract_stat_rows`, `_build_player_meta_map`, `_FIELD_MAP`. Load the FullTime fixture; fake maps from the fixture's teamIds/playerIds.
3. Tests:
   - `test_build_player_meta_map` — `_build_player_meta_map(payload)` returns playerId → {jersey_number, position, is_on_field, is_home, nrlcom_team_id} for every player in both squads; spot-check one known player.
   - `test_extract_stat_rows_field_mapping` — for a known player, the returned row maps `tacklesMade→tackles_made`, `allRunMetres→all_run_metres`, `tries→tries` etc. per `_FIELD_MAP`; `jersey_number`/`position`/`is_on_field` come from player_meta; `is_home` correct; `match_id` is the passed-in value; `s3_archive_key==key`.
   - `test_person_and_team_resolution` — with player_map/team_map populated, `person_id`/`team_id` resolve; with empty maps they are `None` (row still emitted — person_id is nullable).
   - `test_row_count_equals_stat_players` — `len(_extract_stat_rows(...))` == total players across `stats.players.homeTeam` + `.awayTeam`.

**How to verify**
- `pytest tests/unit/scripts/data/populate/test_phase_stats.py -v` — all pass.
- The refactor is behavior-preserving: `grep` confirms `populate_player_match_stats` still UPSERTs via the same `upsert_sql` and returns the same summary keys. `pytest tests/unit/ -q` green.
- `git status`: modified `phase_stats.py` + one new test file.

**Proof notes**
_(implementer fills in)_


### TASK-16: Refactor `phase_team_lists` to a pure `_extract_player_list_rows` + unit tests

Implements PLAN.md § 2026-05-24 Scout Phase 3.5 / Interface / pure extract (team_lists). Depends on TASK-13.

**What**
1. **Behavior-preserving refactor** of `scripts/data/populate/phase_team_lists.py`: extract the inlined **player** row-building (the `for p in team_block["players"]` body, excluding the existence pre-check + INSERT) into a pure `_extract_player_list_rows(payload, match_id, team_map, player_map) -> list[dict]` returning dicts of `{match_id, team_id, player_id, jersey_number, named_position, is_captain}` for every resolvable player (skip players with no `person_id` and teams not in `team_map`, matching current behavior). `populate_team_lists` calls it, then does the existing existence-check + INSERT loop. The **coach** path (`_ensure_coach_person`, DB I/O) stays inline, unchanged — out of unit scope, covered by the prod-run verify.
2. Create `tests/unit/scripts/data/populate/test_phase_team_lists.py`. Tests:
   - `test_extract_player_list_rows` — for the FullTime fixture + populated maps, returns one row per resolvable player; spot-check jersey_number/named_position; `is_captain` true exactly for the player whose id == `team_block["captainPlayerId"]`.
   - `test_skips_unresolved_player` — a playerId not in player_map is omitted.
   - `test_skips_unresolved_team` — a team whose teamId not in team_map contributes no rows.

**How to verify**
- `pytest tests/unit/scripts/data/populate/test_phase_team_lists.py -v` — all pass.
- Refactor behavior-preserving: `populate_team_lists` still does the existence pre-check + INSERT + coach path + returns the same summary keys. `pytest tests/unit/ -q` green.
- `git status`: modified `phase_team_lists.py` + one new test file.

**Proof notes**
_(implementer fills in)_


### TASK-17: Refactor `phase_timeline` to pure `_extract_timeline_rows` + `_extract_official_rows` + unit tests

Implements PLAN.md § 2026-05-24 Scout Phase 3.5 / Interface / pure extract (timeline). Depends on TASK-13.

**What**
1. **Behavior-preserving refactor** of `scripts/data/populate/phase_timeline.py`: extract two pure functions — `_extract_timeline_rows(payload, key, match_id, team_map, player_map) -> list[dict]` (one row per `timeline[]` event: match_id, nrlcom_match_id, sequence, event_type, title, game_seconds, nrlcom_team_id, team_id, nrlcom_player_id, person_id, running_home_score, running_away_score, raw_payload, s3_archive_key) and `_extract_official_rows(payload, key, match_id) -> list[dict]` (one row per `officials[]` with a name: match_id, nrlcom_match_id, first_name, last_name, role, person_id=None, raw_payload, s3_archive_key). `populate_timeline_and_officials` calls both, then UPSERTs via the existing `timeline_sql` / `officials_sql`. No SQL/summary change.
2. Create `tests/unit/scripts/data/populate/test_phase_timeline.py`. Tests:
   - `test_extract_timeline_rows` — `sequence` is 0..N-1 in order; `event_type` defaults to `"Unknown"` when an event has no `type`; `running_home_score`/`running_away_score` map from `homeScore`/`awayScore`; team/player resolve via maps (None when absent); row count == `len(payload["timeline"])`.
   - `test_extract_official_rows` — one row per official with a first or last name; an official with neither is skipped; `role` from `position`; `person_id` is `None`.

**How to verify**
- `pytest tests/unit/scripts/data/populate/test_phase_timeline.py -v` — all pass.
- Refactor behavior-preserving: `populate_timeline_and_officials` still UPSERTs via `timeline_sql`/`officials_sql` and returns the same summary keys. `pytest tests/unit/ -q` green.
- `git status`: modified `phase_timeline.py` + one new test file.

**Proof notes**
_(implementer fills in)_


### TASK-18: Fix the broken `--dry-run` (thread a `commit` flag through the phases)

Implements PLAN.md § 2026-05-24 Scout Phase 3.5 / Interface / `--dry-run` fix. Closes the META known-bug.

**What**
1. Add `commit: bool = True` to each phase function the orchestrator calls in `scripts/data/populate/`: at minimum the 4 match phases (`populate_matches`, `populate_team_lists`, `populate_player_match_stats`, `populate_timeline_and_officials`) and, for consistency, the others (`populate_rounds`, `backfill_identity`, `populate_people_history`, `reresolve_person_ids`, `populate_player_attributes`, `populate_team_standings`, `populate_stat_leaderboards`, `populate_injuries`). Replace every `db.commit()` — both the final commit AND the per-50-archive checkpoint commits in `phase_stats`/`phase_timeline` — with `if commit: db.commit()`.
2. Edit `scripts/data/populate_db_from_s3.py`: pass `commit=not args.dry_run` into every phase call. Keep the existing outer `if args.dry_run: db.rollback()`. (With phases no longer committing under dry-run, the outer rollback now actually discards the work.)
3. Update the `--dry-run` argparse help to: `"Compute counts without committing (phases skip their commits; the transaction is rolled back at the end)."`

**How to verify**
- A test `tests/unit/scripts/data/populate/test_dry_run_flag.py` (or extend an existing one) asserting that each phase function accepts `commit=False` (signature check via `inspect.signature`) — pure-signature test, no DB.
- On the box (or any env with the prod DB + S3): `python -m scripts.data.populate_db_from_s3 --phase matches --seasons 2026 --dry-run` followed by `SELECT count(*) FROM matches WHERE season=2026 AND source='nrl_com'` shows **no change** vs. before the dry-run. Capture both counts in proof notes. (This is the load-bearing check that the META bug is fixed.)
- `grep -n "db.commit()" scripts/data/populate/phase_*.py` shows every occurrence guarded by `if commit:`.
- Update `docs/build/META.md`: change the "`populate_db_from_s3 --dry-run` is broken" entry to record that it's fixed as of this task (commit-flag threaded; outer rollback now effective).
- `git status`: modified phase files + orchestrator + META.md + one new/extended test.

**Proof notes**
_(implementer fills in)_


### TASK-19: Prod populate run + DB verification + docs + run report (Phase 3.5 closure)

Implements PLAN.md § 2026-05-24 Scout Phase 3.5 / Verification (prod populate) + Documentation updates. **Only run after TASK-13→18 are merged and the box has the refactored code.** Runs on the box (needs prod `DATABASE_URL` + S3 creds + deployed code), like the Phase 3 seed. If the box is not yet at the merge commit, tag `[BLOCKED: box not deployed with Phase 3.5 code]` and surface to the human.

**What**
1. On the box, confirm the deployed working tree has the refactored phases (`grep -c _extract_stat_rows /opt/jeromelu/scripts/data/populate/phase_stats.py`). Then run the populate for season 2026 in dependency order — the match phases require `identity` (teams.nrlcom_team_id + people.nrlcom_player_id) and `matches` populated first:
   ```bash
   cd /opt/jeromelu && set -a; . .env; set +a
   python -m scripts.data.populate_db_from_s3 --phase all --seasons 2026 --competition 111
   ```
   (Or run `identity`, `people`, `rounds`, `matches`, `team_lists`, `stats`, `timeline` individually in that order.) Capture the JSON summary (per-phase inserted/updated counts).
2. Verify DB rows (on the box, `docker exec jeromelu-postgres psql -U jeromelu_admin -d jeromelu`):
   ```sql
   SELECT count(*) FROM matches WHERE season=2026 AND source='nrl_com';            -- ≥ the seeded R12 matches
   SELECT count(*) FROM match_team_lists ml JOIN matches m ON m.match_id=ml.match_id WHERE m.season=2026;
   SELECT count(*) FROM player_match_stats pms JOIN matches m ON m.match_id=pms.match_id WHERE m.season=2026;
   SELECT count(*) FROM match_timeline mt JOIN matches m ON m.match_id=mt.match_id WHERE m.season=2026;
   SELECT count(*) FROM match_officials mo JOIN matches m ON m.match_id=mo.match_id WHERE m.season=2026;
   ```
   All non-zero. Spot-check: for one R12 match, `player_match_stats` row count ≈ its squad size (≈34 for both teams). Capture outputs.
3. Docs: create/update `scripts/data/populate/README.md` (phase list, run command, the pure-function test seams, the fixed `--dry-run`); add a note in `docs/operations/data-catalogue/` that the 5 match tables are populated by the `phase_*` extractors from `scout/nrlcom/match-centre/*`.
4. Create + finalise the run report `docs/build/runs/2026-05-24-scout-phase-3.5-nrlcom-extractors.md` (per-task account + verification + decisions + lessons), add its index row, then **remove the Phase 3.5 plan from PLAN.md Active and clear TASK-13→19 from TASKS.md** (run-report ritual).

**How to verify**
- The populate summary shows non-zero inserts for matches/team_lists/stats/timeline/officials (or non-zero existing rows if already populated — idempotent).
- The five `count(*)` queries are all > 0 for season 2026; the spot-check match's stat-row count matches its squad size.
- Run report exists + indexed; PLAN Active no longer lists Phase 3.5; TASKS.md has no TASK-13→19.

**Proof notes**
_(implementer fills in)_


## Completed work

Completed tasks are not kept here. When a task passes review and is checked off, what it delivered is recorded in the active run report under [`docs/build/runs/`](./runs/) and the task is removed from this file. This queue holds only open/in-flight work.
