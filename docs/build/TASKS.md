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

### TASK-03: Add D8 fixture + unit drift tests for `scout/supercoach_settings/`

Implements PLAN.md § 2026-05-24 Phase 2.5 closure / "Files created" / supercoach_settings items 1-2.

**What**
1. Capture canonical response: `curl -s "https://www.supercoach.com.au/$(date +%Y)/api/nrl/classic/v1/settings" | python -m json.tool > tests/fixtures/scout/supercoach_settings/canonical_response.json`. Confirm the file is a JSON object with top-level keys `competition`, `content`, `game`, `system` (and nothing else). File size will be ~15–20KB; that is expected — do not trim. Rationale: the strict model only enforces 4 top-level keys, but the full payload is the diff target when drift surfaces inside nested branches (e.g. `game.experts`).
2. Create `tests/unit/api/scout/test_supercoach_settings_models.py` templated on `tests/unit/api/scout/test_supercoach_roster_models.py`. Three test functions:
   - `test_canonical_fixture_parses(fixture_settings)` — `SuperCoachSettings.model_validate(fixture_settings)` returns without error. Sanity asserts on the parsed object: `parsed.system["currency"] == "AUD"`; `parsed.system["timezone"] == "Australia/Sydney"`; `"current_round" in parsed.competition`; `"player_stats" in parsed.game`.
   - `test_unknown_top_level_field_raises(fixture_settings)` — `deepcopy`, set `bad["loot_boxes"] = {}`, expect `ValidationError` whose message contains `"loot_boxes"`. This is the load-bearing D8 envelope guard test.
   - `test_missing_required_top_level_raises(fixture_settings)` — `del bad["game"]`, expect `ValidationError` containing `"game"`.
3. Use the existing `fixtures_dir` fixture from `tests/conftest.py`. The `fixture_settings` is a single dict (not a list — settings is an object envelope), so the fixture function returns `json.loads(path.read_text(encoding="utf-8"))` directly.

**How to verify**
- `pytest tests/unit/api/scout/test_supercoach_settings_models.py -v` — all three tests pass.
- `pytest tests/unit/api/scout/ -v` — full scout unit suite stays green.
- `git status` shows exactly two new files. The fixture is pretty-printed.

**Proof notes**
_(implementer fills in)_


### TASK-04: Add D8 live integration drift tests (classic + draft) for `scout/supercoach_settings/`

Implements PLAN.md § 2026-05-24 Phase 2.5 closure / "Files created" / supercoach_settings item 3.

**What**
1. Create `tests/integration/scout/test_supercoach_settings_response_shape.py` templated on `tests/integration/scout/test_supercoach_roster_response_shape.py`. Mirror its D8 docstring framing.
2. Two parameterised tests (or two functions — either is fine; prefer `@pytest.mark.parametrize("mode", ["classic", "draft"])` on a single function for brevity), both gated on `SCOUT_DRIFT_LIVE=1`:
   - `test_live_supercoach_settings_shape(mode)` — calls `fetch_supercoach_settings(season=date.today().year, mode=mode)` from `app.scout.supercoach_settings.fetcher`, then `SuperCoachSettings.model_validate(raw)`. Wrap in `try/except (SuperCoachSettingsFetchError, ValidationError)` → `pytest.fail` with message: `f"SuperCoach settings live drift test failed (mode={mode}) — upstream shape has changed.\nError: {type(e).__name__}: {e}\nFix path: review the response, update app.scout.supercoach_settings.models (top-level envelope only), regenerate the fixture, commit with a note on what the upstream changed."`
   - Sanity asserts after parse: `parsed.system["timezone"] == "Australia/Sydney"`; `len(parsed.game) > 50` (the `game` dict has 69+ sub-keys per the README — guards against an empty stub response).
3. Draft mode is included specifically because the Makefile / fetcher already support it and the upstream draft endpoint has independent drift risk. **Production cron does not run draft** — this test is the only guardrail against silent draft-mode breakage, so it is non-negotiable.

**How to verify**
- Without the env flag: both parameterised cases show as skipped.
- With the env flag: `SCOUT_DRIFT_LIVE=1 pytest tests/integration/scout/test_supercoach_settings_response_shape.py -v` shows both `[classic]` and `[draft]` cases passing.
- Locally pollute `SuperCoachSettings` (e.g. rename `game` → `gameplay`), re-run live mode → both cases must fail with messages naming `game`. Revert.
- `git status` shows exactly one new file.

**Proof notes**
_(implementer fills in)_


### TASK-05: Extend `scripts/scout-refresh.sh` + add cron lines for SC teams + settings

Implements PLAN.md § 2026-05-24 Phase 2.5 closure / "Cron schedule".

**What**
1. Edit `scripts/scout-refresh.sh`: extend the `case "$JOB"` block (currently lines 31–35, `channel-stats|videos`) to add two more cases:
   - `supercoach-teams)    ENDPOINT="supercoach-teams" ;;`
   - `supercoach-settings) ENDPOINT="supercoach-settings" ;;`
   The script's existing URL template at line 41 (`https://${API_HOST}/api/admin/scout/${ENDPOINT}`) prepends `/api/admin/scout/` automatically — the ENDPOINT value must NOT include a leading `scout/`. The two new admin routes live at `/api/admin/scout/supercoach-teams` and `/api/admin/scout/supercoach-settings`, so `ENDPOINT="supercoach-teams"` is correct (verified against script line 41 and Makefile lines 371, 377).
   Also update the usage message on line 34 from `usage: $0 {channel-stats|videos}` to `usage: $0 {channel-stats|videos|supercoach-teams|supercoach-settings}`.
   **No other changes** — the curl block, `--resolve` loopback, `--max-time 3600`, and log line format are reused as-is so the existing `cron_report.py` parsing keeps working.
2. Edit `scripts/cron.d/jeromelu`: insert two new cron lines after the existing `15 23 * * *` videos refresh entry (currently line 31). Use this exact block, preserving the file's existing comment style:

   ```cron
   # Weekly SuperCoach teams refresh — Mondays 23:30 UTC = Tuesday 09:30 AEST.
   # Tiny payload (17 rows, ~3KB). Refreshes teams.metadata_json.supercoach
   # via /api/admin/scout/supercoach-teams. Audit row under agent_id='scout'.
   30 23 * * 1     ubuntu  /opt/jeromelu/scripts/scout-refresh.sh supercoach-teams

   # Weekly SuperCoach settings snapshot — Mondays 23:35 UTC = Tuesday 09:35 AEST.
   # ~15KB payload. Captures game rules per season into sc_settings (classic
   # mode only — draft is on-demand via make scout-supercoach-settings MODE=draft).
   35 23 * * 1     ubuntu  /opt/jeromelu/scripts/scout-refresh.sh supercoach-settings
   ```
3. Do **not** touch `/etc/cron.d/jeromelu` on the prod box directly. The deploy step (`scripts/lightsail-deploy.sh`) syncs the file from the repo on next deploy. Confirm that's the case by grepping the deploy script for `cron.d/jeromelu` and noting the copy step in the proof notes.

**How to verify**
- `bash -n scripts/scout-refresh.sh` — no syntax errors.
- Run the wrapper locally with the new arg pointed at a non-existent host to prove the case clause matches: `JOB=supercoach-teams ADMIN_KEY=test API_HOST=invalid.local bash -x scripts/scout-refresh.sh supercoach-teams 2>&1 | head -20` — should show the script reaching the curl call (curl will fail at DNS; that proves the case matched). Repeat for `supercoach-settings`.
- `crontab -T scripts/cron.d/jeromelu` (if a `cron` package is locally available) or visual diff vs the existing entries — each new line has 5 timing fields, user `ubuntu`, absolute path to the wrapper.
- `grep -n cron.d/jeromelu scripts/lightsail-deploy.sh` returns a sync line, proving deploy will publish the change. Quote the relevant lines in proof notes.
- `git status` shows exactly two modified files: the wrapper and the crontab. No new files.

**Proof notes**
_(implementer fills in: bash -n output, dry-run output, lightsail-deploy.sh grep, commit SHA)_


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
