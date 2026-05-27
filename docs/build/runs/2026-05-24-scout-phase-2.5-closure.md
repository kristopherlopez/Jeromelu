# Scout Phase 2.5 closure — SC teams + settings

**Date:** 2026-05-24 · **Status:** 🟢 Shipped · **Plan:** Scout Phase 2.5 closure · **Tasks:** TASK-01 → TASK-06

**TL;DR** — Took `scout/supercoach_teams/` and `scout/supercoach_settings/` from "code shipped but untested, unscheduled, ad-hoc-seeded" to charter-compliant and Shipped — matching the discipline already in place for `supercoach_roster/` (Phase 1) and `supercoach_stats/` (Phase 2). Drift tests, weekly cron, a verified prod seed for season 2026, and docs flipped to Shipped. One bullet outstanding: confirming the first cron fire next Monday.

---

## What was completed

### TASK-01 — SC teams: drift fixture + unit tests (`fa0cc8f`)
Captured the live `/teams` response (17 NRL clubs) to `tests/fixtures/scout/supercoach_teams/canonical_response.json` (pretty-printed, 223 lines / 5.4KB; every object carries `id`/`abbrev`/`feed_name`/`name`/`competition`, 17 distinct abbrevs, all NRL competition id 2). Added `tests/unit/api/scout/test_supercoach_teams_models.py` (templated on the roster test) with four tests against the strict `SuperCoachTeam` model: canonical parse + three negatives — unknown team field (`is_new_franchise`), unknown nested-competition field (`is_super_league`), missing required field (`del abbrev`).
**Proof:** 4 passed; full scout unit suite 28 passed (no regression). Reviewer PASS.

### TASK-02 — SC teams: live drift test (`023716b`)
Added `tests/integration/scout/test_supercoach_teams_response_shape.py` — env-flagged (`SCOUT_DRIFT_LIVE=1`) test that hits the real `/teams` endpoint and strict-parses every team; on `SuperCoachTeamsFetchError`/`ValidationError` it fails loudly with the operator fix-path. Sanity asserts: 16–18 teams, unique abbrevs, all competition id 2. Skipped in CI by default.
**Proof:** skipped without the flag; 1 passed live; deliberate-break (`is_relegated` added to `SCCompetition`) failed naming `competition.is_relegated`, then reverted clean. Reviewer PASS.

### TASK-03 — SC settings: drift fixture + unit tests (`b602e88`)
Captured the live `/settings` response (the four top-level groups `competition`/`content`/`game`/`system`; ~38KB, 1189 lines) to `tests/fixtures/scout/supercoach_settings/canonical_response.json`. Added `tests/unit/api/scout/test_supercoach_settings_models.py` with three tests: canonical parse (smoke-asserts currency AUD, timezone Australia/Sydney, `current_round` ∈ competition, `player_stats` ∈ game; `game` has 69 sub-keys), the load-bearing top-level envelope guard (unknown key `loot_boxes`), and a missing-required-group negative (`del game`).
**Proof:** 3 passed; full scout unit suite 31 passed. Reviewer PASS-with-concerns (fixture ~2× the size estimate — kept untrimmed per spec; non-blocking).

### TASK-04 — SC settings: live drift tests, classic + draft (`fa16afa`)
Added `tests/integration/scout/test_supercoach_settings_response_shape.py`, parameterised over `classic` and `draft` modes, env-flagged. Draft is included deliberately — prod cron only refreshes classic, so this is the sole guardrail against silent draft-mode breakage. Strict-parses the top-level envelope; sanity asserts timezone + `len(game) > 50`.
**Proof:** both modes skipped without the flag; both passed live (live `game` sub-keys: classic 69, draft 54 — both clear the >50 gate); deliberate break (`game`→`gameplay`) failed both naming `game`, then reverted. Reviewer PASS-with-concerns (thin draft margin noted; to-spec).

### TASK-05 — scheduling: wrapper + cron (`b031fff`)
Added `supercoach-teams` and `supercoach-settings` cases to `scripts/scout-refresh.sh` (mapping to `/api/admin/scout/supercoach-{teams,settings}`) and two weekly cron lines to `scripts/cron.d/jeromelu`: teams **Mon 23:30 UTC**, settings **Mon 23:35 UTC** (classic only — draft stays on-demand). Synced the wrapper's usage/header text. Confirmed `scripts/lightsail-deploy.sh` installs the crontab to `/etc/cron.d/jeromelu` (lines 58–60).
**Proof:** `bash -n` clean; dry-runs show both case clauses matching and building the correct URL; cron lines well-formed. Reviewer PASS.

### TASK-06 — prod seed + verification + doc flips (`8ed6e37`)
Seeded prod for season 2026 (run on the box via loopback — see deviations): teams **17/17 matched**, classic + draft settings snapshotted (each `"ok": true`). Verified the three S3 archives landed today-dated and the DB rows wrote (`sc_settings` ×2; 17 `teams` with `supercoach` metadata). Regenerated the classic/draft settings S3 profile docs (`docs/operations/data-sources/supercoach/`), flipped the roadmap Phase 2.5 heading + bullets and the charter SC rows to ✅ Shipped, and added `## Tests` sections to both pipeline READMEs.
**Proof:** see Verification below. Reviewer PASS-with-concerns (all non-blocking; S3 independently reproduced).

---

## How we know it's done
- **Tests:** scout unit suite green (31 tests); live drift tests pass against the real endpoints; deliberate-break runs confirm each fails loudly naming the drifted field.
- **S3** (`aws s3 ls`, reviewer-reproduced): `classic/teams/2026.json` (3176 B), `classic/settings/2026/20260524.json` (16994 B), `draft/settings/2026/20260524.json` (15760 B) — all dated 2026-05-24.
- **DB** (prod box, `psql`): `sc_settings` 2 rows season 2026 dated today (classic 16994 B, draft 15760 B); 17 `teams` carry distinct `supercoach` abbrevs.

## Decisions & deviations
- **Seeded on the prod box** via `curl --resolve api.jeromelu.ai:443:127.0.0.1` — the box can't hairpin-NAT to its own public IP.
- **`ADMIN_KEY` not reachable via SSM** (IAM denies `ssm:GetParameter` to the human user); pulled from `/opt/jeromelu/.env` over Lightsail SSH instead.
- Endpoints return `matched`/`upserted_id`, **not** the spec-anticipated `s3_archive_key`; used `aws s3 ls` as the authoritative S3 proof. Reviewer confirmed harmless (the key is recorded in the audit detail + `sc_settings`, not the HTTP body).

## Outstanding
- ☑ **First cron fire confirmed (2026-05-27, verified by the implementer session).** `/var/log/jeromelu/scout-refresh.log` on prod shows both jobs ran clean on **Mon 2026-05-25**:
  - `[2026-05-25T23:30:01Z] supercoach-teams status=200 … "ok":true … "fetched":17,"matched":17,"unknown_abbrev":[],"missing_team_row":[]`
  - `[2026-05-25T23:35:01Z] supercoach-settings status=200 … "ok":true … "mode":"classic","upserted_id":"b4744204-fe34-4aab-ad35-e1b139d913a3"`

  Status set to fully Shipped; plan removed from PLAN.md's Active section.

## Lessons → promoted to META
- On-box admin API calls need `--resolve` (hairpin-NAT). → META "On-box admin API calls need `--resolve`".
- Prod secrets come from the box, not SSM (human user lacks `ssm:GetParameter`). → META "Prod secrets come from the box, not SSM".

## Commits
`fa0cc8f` · `023716b` · `b602e88` · `fa16afa` · `b031fff` · `8ed6e37` (plus per-task checkoff commits). All on `master`.
