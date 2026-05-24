# Jaromelu Task Queue

Persistent queue for the long-lived implementer session. The implementer reads top-down, completes one task at a time, dispatches `adversarial-reviewer` against the diff + task + plan, and only checks off after the review passes.

## Format

Each task is a level-3 heading with three labelled blocks:

- **What** — exactly what to do. References a section of `PLAN.md`.
- **How to verify** — concrete checks. Commands, files, expected output. Bar: "if satisfied exactly as written, the result is trustworthy."
- **Proof notes** — filled in by the implementer after completion. Commands run, output observed, files changed, commit SHA. Empty until done.

Mark as `[x]` only after `adversarial-reviewer` passes. Move completed tasks to the bottom section.

### Tags

Prefix the title with optional tags in square brackets:

- `[P0]`, `[P1]`, `[P2]`, `[P3]` — severity (from `issue-triager`)
- `[BLOCKED: reason]` — implementer hit a wall; needs human input

---

## Open tasks

### TASK-06: One-time S3 seed + DB verification + roadmap/charter status flip + S3 profile docs refresh

Implements PLAN.md § 2026-05-24 Phase 2.5 closure / "One-time S3 seed run" + "Documentation updates". This is the closure task — only run after TASK-01 through TASK-05 are merged and the cron is deployed.

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


---

## Completed tasks

### [x] TASK-01: Add D8 fixture + unit drift tests for `scout/supercoach_teams/`

Implements PLAN.md § 2026-05-24 Phase 2.5 closure / "Files created" / supercoach_teams items 1-2.

**Proof notes**
- **Fixture captured** via `curl -s "https://www.supercoach.com.au/$(date +%Y)/api/nrl/classic/v1/teams" | python -m json.tool > tests/fixtures/scout/supercoach_teams/canonical_response.json` (season=2026, current calendar year). File is **pretty-printed**: 223 lines / 5442 bytes (≫ 17). Validated programmatically: JSON `list` of **17** objects, each carrying `id`/`abbrev`/`feed_name`/`name`/`competition`; **17** unique abbrevs; every `competition.id == 2`; every `competition.name == "NRL"`. (The nested `competition.season` is `null` in the live payload — faithful capture; the model permits `season: int | None`.)
- **Test module** `tests/unit/api/scout/test_supercoach_teams_models.py` created, templated on `test_supercoach_roster_models.py` — same `@pytest.fixture(scope="module")` + `fixtures_dir` pattern, imports `SuperCoachTeam` from `app.scout.supercoach_teams.models`. Four functions in spec order: `test_canonical_fixture_parses`, `test_unknown_field_on_team_raises` (`is_new_franchise`), `test_unknown_field_on_nested_competition_raises` (`is_super_league`), `test_missing_required_field_raises` (`del abbrev`).
- `pytest tests/unit/api/scout/test_supercoach_teams_models.py -v` → **4 passed** in 1.87s.
- `pytest tests/unit/api/scout/ -v` → **28 passed** in 1.34s (24 pre-existing + 4 new; no regression).
- `git status` after staging showed exactly the two task artifacts. Pre-existing concurrent-session changes (`services/api/app/analyst/identify_voice.py` modified, `services/web/.claude/` untracked) were left untouched and unstaged.
- **adversarial-reviewer verdict: PASS** — no Blockers, no Concerns (one awareness note re `season: null`, non-blocking).
- **Commit:** `fa0cc8f` — `test(scout): add D8 fixture + unit drift tests for supercoach_teams [skip-simplify]`. Pushed to `master`.

### [x] TASK-02: Add D8 live integration drift test for `scout/supercoach_teams/`

Implements PLAN.md § 2026-05-24 Phase 2.5 closure / "Files created" / supercoach_teams item 3.

**Proof notes**
- **Created** `tests/integration/scout/test_supercoach_teams_response_shape.py`, templated on `test_supercoach_roster_response_shape.py` (D8 / env-flag / operator-fix-path docstring framing preserved). Single test `test_live_supercoach_teams_shape`, gated on `os.environ.get("SCOUT_DRIFT_LIVE") == "1"`. Fetch + parse both inside one `try/except (SuperCoachTeamsFetchError, ValidationError)` → `pytest.fail` with the exact spec message (incl. fixture path). Three sanity asserts: `16 <= len(parsed) <= 18`, unique-abbrev count, `{competition.id} == {2}`.
- **Skip mode:** `pytest tests/integration/scout/test_supercoach_teams_response_shape.py -v` → **1 skipped**, reason `Set SCOUT_DRIFT_LIVE=1 to run the live-endpoint drift test`.
- **Live mode:** `SCOUT_DRIFT_LIVE=1 pytest ... -v` → **1 passed** in 1.54s (real SC endpoint hit).
- **Deliberate break:** temporarily added `is_relegated: bool` to `SCCompetition` in `models.py` → live run **FAILED** naming `competition.is_relegated` in the message. Reverted; `git diff models.py` is empty.
- `git status` showed exactly one new file (plus untouched concurrent-session changes).
- **adversarial-reviewer verdict: PASS** — no Blockers, no Concerns.
- **Commit:** `023716b` — `test(scout): add D8 live integration drift test for supercoach_teams [skip-simplify]`. Pushed to `master`.

### [x] TASK-03: Add D8 fixture + unit drift tests for `scout/supercoach_settings/`

Implements PLAN.md § 2026-05-24 Phase 2.5 closure / "Files created" / supercoach_settings items 1-2.

**Proof notes**
- **Fixture captured** via `curl -s "https://www.supercoach.com.au/$(date +%Y)/api/nrl/classic/v1/settings" | python -m json.tool > tests/fixtures/scout/supercoach_settings/canonical_response.json` (season=2026). **Pretty-printed: 1189 lines / 38900 bytes (~38KB)** — note this is ~2× the planner's "~15–20KB" estimate; kept untrimmed per the spec. Validated: JSON `dict` whose top-level keys are **exactly** `{competition, content, game, system}` (nothing else, so the `extra="forbid"` envelope parses); `system.currency == "AUD"`; `system.timezone == "Australia/Sydney"`; `current_round` ∈ `competition`; `player_stats` ∈ `game`; `game` has **69** sub-keys.
- **Test module** `tests/unit/api/scout/test_supercoach_settings_models.py` created, templated on `test_supercoach_roster_models.py`, imports `SuperCoachSettings` from `app.scout.supercoach_settings.models`. `fixture_settings` returns a single dict via `json.loads(...)` (not a list); uses the `fixtures_dir` conftest fixture. Three functions: `test_canonical_fixture_parses` (with the four smoke asserts), `test_unknown_top_level_field_raises` (envelope guard, `loot_boxes`), `test_missing_required_top_level_raises` (`del game`).
- `pytest tests/unit/api/scout/test_supercoach_settings_models.py -v` → **3 passed** in 1.27s.
- `pytest tests/unit/api/scout/ -q` → **31 passed** in 1.40s (28 prior + 3 new; no regression).
- `git status` showed exactly the two task artifacts staged (plus untouched concurrent-session changes).
- **adversarial-reviewer verdict: PASS WITH CONCERNS** — both concerns non-blocking and required no code change: (1) fixture ~38KB vs estimate — recorded above; (2) proof notes empty at review time — filled here before checkoff.
- **Commit:** `b602e88` — `test(scout): add D8 fixture + unit drift tests for supercoach_settings [skip-simplify]`. Pushed to `master`.

### [x] TASK-04: Add D8 live integration drift tests (classic + draft) for `scout/supercoach_settings/`

Implements PLAN.md § 2026-05-24 Phase 2.5 closure / "Files created" / supercoach_settings item 3.

**Proof notes**
- **Created** `tests/integration/scout/test_supercoach_settings_response_shape.py`, templated on `test_supercoach_roster_response_shape.py` (D8 / env-flag framing preserved, plus a draft-mode-rationale paragraph). Single function `test_live_supercoach_settings_shape(mode)` with `@pytest.mark.parametrize("mode", ["classic", "draft"])`, gated on `os.environ.get("SCOUT_DRIFT_LIVE") == "1"`. Fetch + parse both inside one `try/except (SuperCoachSettingsFetchError, ValidationError)` → `pytest.fail` with the exact spec message (reviewer confirmed runtime-rendered string matches char-for-char). Sanity asserts: `system["timezone"] == "Australia/Sydney"`, `len(game) > 50`.
- **Skip mode:** `pytest tests/integration/scout/test_supercoach_settings_response_shape.py -v -rs` → **2 skipped** (`[classic]`, `[draft]`), reason `Set SCOUT_DRIFT_LIVE=1 to run the live-endpoint drift test`.
- **Live mode:** `SCOUT_DRIFT_LIVE=1 pytest ... -v` → **2 passed** in 2.24s (real SC endpoint, both modes). Observed live `game` sub-key counts: classic **69**, draft **54** — both clear the `> 50` gate. Note (reviewer concern, non-blocking): the draft margin is thin (54 vs threshold 50); a modest upstream trim of draft's `game` block could trip the assert before genuine envelope drift. Acceptable as the intended conservative stub-guard; left to-spec.
- **Deliberate break:** temporarily renamed `game` → `gameplay` in `SuperCoachSettings` → both live cases **FAILED** with messages naming `game` (extra-forbidden) and `gameplay` (missing-required). Reverted; `git diff models.py` is empty.
- `git status` showed exactly one new file (plus untouched concurrent-session changes).
- **adversarial-reviewer verdict: PASS WITH CONCERNS** — both non-blocking (proof notes pending at review time → filled here; thin draft margin → recorded).
- **Commit:** `fa16afa` — `test(scout): add D8 live integration drift tests (classic+draft) for supercoach_settings [skip-simplify]`. Pushed to `master`.

### [x] TASK-05: Extend `scripts/scout-refresh.sh` + add cron lines for SC teams + settings

Implements PLAN.md § 2026-05-24 Phase 2.5 closure / "Cron schedule".

**Proof notes**
- **`scripts/scout-refresh.sh`:** added two case clauses (`supercoach-teams) ENDPOINT="supercoach-teams"`, `supercoach-settings) ENDPOINT="supercoach-settings"` — no leading `scout/`, so the URL template yields `/api/admin/scout/supercoach-{teams,settings}`). Updated the `echo "usage: ..."` message and the file-header `# Usage:` comment to list the two new args (header sync = documentation discipline; reviewer explicitly approved as in-spirit, not out-of-spec). Curl block / `--resolve` / `--max-time 3600` / log-line format untouched.
- **`scripts/cron.d/jeromelu`:** inserted the spec's exact two-block (weekly `30 23 * * 1` teams + `35 23 * * 1` settings, user `ubuntu`, absolute wrapper paths) immediately after the `15 23 * * *` videos entry.
- `bash -n scripts/scout-refresh.sh` → clean (no syntax errors).
- Dry-run `JOB=supercoach-teams ... bash -x ... supercoach-teams` → trace shows `case` matched, `ENDPOINT=supercoach-teams`, `API_URL=https://api.jeromelu.ai/api/admin/scout/supercoach-teams`, reached curl (CURL_RC=7 at connect — proves the clause matched). Same for `supercoach-settings` → `API_URL=.../supercoach-settings`.
- Cron lines verified: 5 timing fields + `ubuntu` + absolute path each.
- `grep -n cron.d/jeromelu scripts/lightsail-deploy.sh` → lines 59–60; the sync is `sudo -n install -m 0644 -o root -g root /opt/jeromelu/scripts/cron.d/jeromelu /etc/cron.d/jeromelu` (lines 58–60), and line 64 `chmod +x /opt/jeromelu/scripts/*.sh`. So the wrapper arg + cron lines publish to `/etc/cron.d/jeromelu` on next deploy; prod crontab is never hand-edited.
- `git status` showed exactly two modified files (the wrapper + crontab), no new files (plus untouched concurrent-session changes).
- **adversarial-reviewer verdict: PASS** — no Blockers, no Concerns; header-comment sync explicitly approved.
- **Commit:** `b031fff` — `feat(scout): wire SC teams + settings into scout-refresh.sh + cron [skip-simplify]`. Pushed to `master`.
