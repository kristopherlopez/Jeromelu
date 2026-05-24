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


## Completed work

Completed tasks are not kept here. When a task passes review and is checked off, what it delivered is recorded in the active run report under [`docs/build/runs/`](./runs/) and the task is removed from this file. This queue holds only open/in-flight work.
