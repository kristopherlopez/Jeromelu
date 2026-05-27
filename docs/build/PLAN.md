# Jaromelu Build Plan

This document holds active and historical plan docs that drive the persistent task queue in [TASKS.md](./TASKS.md). Plans are written by the `planner` agent (or a planning session) and consumed by the `implementer`.

## What good looks like

A good plan doc is:

- **Self-contained** — readable cold by an implementer with no prior conversation context.
- **Interface-level** — names file paths, types, function signatures, table columns, API shapes, env vars. No "figure out the right shape".
- **End-to-end verifiable** — explicit "how do we know this is done" strategy, runnable from the outside (curl, CLI, screenshot, query).
- **Iterated to high quality** before any task is appended. A plan that ships fuzzy tasks burns implementer time on re-asking.

Plans link to the tasks they spawn. Tasks link back to the plan section they implement.

---

## Active plan

## 2026-05-24: Scout Phase 2.5 closure — SC teams + settings

**Goal:** Take `scout/supercoach_teams/` and `scout/supercoach_settings/` from "code shipped, untested, unscheduled, S3 seeded ad-hoc on 2026-05-12" to **charter-compliant, scheduled, S3-seeded, Shipped** — matching the discipline already in place for `supercoach_roster/` (Phase 1) and `supercoach_stats/` (Phase 2).

**Constraints:**

- Charter D8 (strict-parse + fixture drift tests): every Scout module ships with `tests/fixtures/scout/<pipeline>/canonical_response.json`, strict Pydantic models (`extra='forbid'`), a fixture-mode unit test, and an env-flagged (`SCOUT_DRIFT_LIVE=1`) live-mode integration test that hits the real endpoint. No exceptions for the small siblings.
- Charter D9 (folder layout) — already satisfied; do not refactor.
- Charter D10 (S3-first) — already satisfied; the route writes raw JSON to S3 before DB.
- Charter D13 (DB extractors downstream) — settings writes `sc_settings` via the route. Teams patches `teams.metadata_json.supercoach` via the route.
- META: `make migrate` is the only path to apply migration 055 (already applied per "verified current state").
- META: session-scoped staging — implementer must `git add` only files this task created/modified.
- Cron lives in `scripts/cron.d/jeromelu` (installed to `/etc/cron.d/jeromelu` by `scripts/lightsail-deploy.sh`). Wrappers live in `scripts/scout-refresh.sh` pattern. The implementer must extend the wrapper or add a sister script — **do not** hand-edit the deployed crontab.
- Roadmap acceptance for Phase 2.5 closure: *"Run once with current season → S3 archive is complete for the SC surface."* Includes weekly forward-cron schedule.

**Interface:**

### Files created (per pipeline)

For `supercoach_teams`:

1. `tests/fixtures/scout/supercoach_teams/canonical_response.json` — **full** captured response (17 teams, ~3KB). Capture command: `curl -s "https://www.supercoach.com.au/2026/api/nrl/classic/v1/teams" > tests/fixtures/scout/supercoach_teams/canonical_response.json`. Pretty-print with `python -m json.tool` for diff readability.
2. `tests/unit/api/scout/test_supercoach_teams_models.py` — templated **exactly** on `tests/unit/api/scout/test_supercoach_roster_models.py`. Four cases:
   - `test_canonical_fixture_parses` — every team parses through `SuperCoachTeam`, expect `len(parsed) == 17`, expect all 17 distinct `abbrev` values, expect every `competition.id == 2` (NRL).
   - `test_unknown_field_on_team_raises` — add `bad["is_new_franchise"] = True`, expect `ValidationError` mentioning `is_new_franchise`.
   - `test_unknown_field_on_nested_competition_raises` — add `bad["competition"]["is_super_league"] = False`, expect `ValidationError` mentioning `is_super_league`.
   - `test_missing_required_field_raises` — `del bad["abbrev"]`, expect `ValidationError` mentioning `abbrev`.
3. `tests/integration/scout/test_supercoach_teams_response_shape.py` — templated on `test_supercoach_roster_response_shape.py`. One test: `test_live_supercoach_teams_shape`, gated on `SCOUT_DRIFT_LIVE=1`. Calls `fetch_supercoach_teams(season=date.today().year)`, parses every row through `SuperCoachTeam`, asserts `16 <= len(teams) <= 18` and `len({t.abbrev for t in teams}) == len(teams)` (no duplicates). Failure message: *"Fix path: review the response, update `app.scout.supercoach_teams.models`, regenerate the fixture under `tests/fixtures/scout/supercoach_teams/canonical_response.json`, commit with a note on what the upstream changed."*

For `supercoach_settings`:

1. `tests/fixtures/scout/supercoach_settings/canonical_response.json` — **full** captured response (~15KB). Capture command: `curl -s "https://www.supercoach.com.au/2026/api/nrl/classic/v1/settings" > tests/fixtures/scout/supercoach_settings/canonical_response.json` then `python -m json.tool` rewrite for diff readability. Rationale for full payload: model only enforces 4 top-level keys, but the fixture is the diff target when drift surfaces inside `game.experts.*` or `game.competitions[*]`.
2. `tests/unit/api/scout/test_supercoach_settings_models.py` — templated on `test_supercoach_roster_models.py`. Three cases:
   - `test_canonical_fixture_parses` — fixture parses through `SuperCoachSettings`. Sanity asserts: `competition`, `content`, `game`, `system` are all dicts; `system["currency"] == "AUD"`; `system["timezone"] == "Australia/Sydney"`.
   - `test_unknown_top_level_field_raises` — `bad["loot_boxes"] = {}` at top level, expect `ValidationError` mentioning `loot_boxes`. (Negates the D8 envelope guard.)
   - `test_missing_required_top_level_raises` — `del bad["game"]`, expect `ValidationError` mentioning `game`.
3. `tests/integration/scout/test_supercoach_settings_response_shape.py` — templated on `test_supercoach_roster_response_shape.py`. **Two** parameterised live tests (`SCOUT_DRIFT_LIVE=1` gated): one for `mode="classic"`, one for `mode="draft"` — because the Makefile / fetcher both support `mode` and the upstream draft endpoint has independent drift risk. Both call `fetch_supercoach_settings(season=date.today().year, mode=mode)` then `SuperCoachSettings.model_validate(raw)`. Failure message: *"Fix path: review the response, update `app.scout.supercoach_settings.models` (top-level envelope only), regenerate the fixture, commit with a note on what the upstream changed."*

### Cron schedule

Add two lines to `scripts/cron.d/jeromelu` immediately after the existing scout-refresh entries (current line 31). Weekly cadence per the README of each module ("Weekly (rarely changes)") and per the roadmap entry ("weekly cadence"):

```cron
# Weekly SuperCoach teams refresh — Mondays 23:30 UTC = Tuesday 09:30 AEST.
# Tiny payload (17 rows, ~3KB). Refreshes teams.metadata_json.supercoach.
30 23 * * 1     ubuntu  /opt/jeromelu/scripts/scout-refresh.sh supercoach-teams

# Weekly SuperCoach settings snapshot — Mondays 23:35 UTC = Tuesday 09:35 AEST.
# ~15KB payload. Captures game rules per season into sc_settings (classic mode).
35 23 * * 1     ubuntu  /opt/jeromelu/scripts/scout-refresh.sh supercoach-settings
```

Extend `scripts/scout-refresh.sh` so the `case "$JOB"` statement (currently `channel-stats|videos`) also accepts `supercoach-teams` (`ENDPOINT="supercoach-teams"`) and `supercoach-settings` (`ENDPOINT="supercoach-settings"`). The script's existing URL template at line 41 (`https://${API_HOST}/api/admin/scout/${ENDPOINT}`) prepends `/api/admin/scout/` automatically, so the ENDPOINT value must NOT include a leading `scout/`. Also update the usage message on line 34 to include the new job names. No other changes — same curl pattern, same loopback `--resolve`, same `--max-time 3600`, same log line format to `/var/log/jeromelu/scout-refresh.log`.

**Why not extend `cron_report.py`:** the existing report already greps `SCOUT_LOG = "/var/log/jeromelu/scout-refresh.log"` and reports per-job status. Adding more jobs to the same log file means they show up in the digest automatically. The report's per-job parsing must be checked against the new job names (see task verification).

**Why classic-only weekly cron, not draft:** roadmap line 44 marks `supercoach_draft_*` as *"🟡 optional — Phase deferred"*. The route accepts `?mode=draft` and the drift test covers it (so we'd know if it broke), but production cron is classic only. Operators can `make scout-supercoach-settings MODE=draft` on demand.

### One-time S3 seed run (post-merge)

After CI passes and the implementer (or human) ships the cron, run once against prod with the current season:

```bash
make scout-supercoach-teams ADMIN_KEY=$ADMIN_KEY SEASON=2026 API=https://api.jeromelu.ai
make scout-supercoach-settings ADMIN_KEY=$ADMIN_KEY SEASON=2026 API=https://api.jeromelu.ai
make scout-supercoach-settings ADMIN_KEY=$ADMIN_KEY SEASON=2026 MODE=draft API=https://api.jeromelu.ai
```

Verify the seed lands by listing the bucket:

```bash
aws s3 ls s3://jeromelu-clean-documents/scout/supercoach/classic/teams/
aws s3 ls s3://jeromelu-clean-documents/scout/supercoach/classic/settings/2026/
aws s3 ls s3://jeromelu-clean-documents/scout/supercoach/draft/settings/2026/
```

Each should show today's-dated keys (teams → `2026.json`; settings → `2026/YYYYMMDD.json`). Verify DB rows:

```bash
make db-shell
=> SELECT season, captured_date, mode FROM sc_settings ORDER BY captured_at DESC LIMIT 5;
=> SELECT slug, metadata_json->'supercoach'->>'abbrev' FROM teams WHERE metadata_json ? 'supercoach' LIMIT 5;
```

`sc_settings` should have the two fresh rows (2026 classic + 2026 draft, dated today). `teams.metadata_json.supercoach` should be populated on all 17 NRL clubs.

**Note:** the 2026-05-12 manual captures already exist in S3 (per `docs/operations/data-sources/supercoach/classic-settings.md`); the seed re-run is to (a) prove the endpoint works end-to-end post-test, (b) refresh stale captures, (c) prove the cron'd job will succeed when it fires.

**Verification strategy:**

- **End-to-end:** `make test` passes in CI (fixture-mode unit tests for both pipelines). `SCOUT_DRIFT_LIVE=1 pytest tests/integration/scout/test_supercoach_teams_response_shape.py tests/integration/scout/test_supercoach_settings_response_shape.py` passes locally before merge. After deploy, the one-time seed runs above complete cleanly. After the first Monday post-deploy, `/var/log/jeromelu/scout-refresh.log` shows two new `[ts] supercoach-teams status=200 ...` and `[ts] supercoach-settings status=200 ...` lines, and the next morning's cron-health email lists both jobs in the digest. The `sc_settings` table grows by one row each week (or stays flat if no upstream change + same-day re-run).
- **Tests:** unit tier under `tests/unit/api/scout/test_supercoach_{teams,settings}_models.py` (drift envelope); integration tier under `tests/integration/scout/test_supercoach_{teams,settings}_response_shape.py` (live drift, env-flagged). No eval tier — deterministic fetchers, per charter "no eval suite for Scout".

**Documentation updates:**

- `docs/agents/crew/scout/roadmap.md` line 58: change Phase 2.5 heading from "Bronze (S3-first) retrofit ✅ + lightweight SC siblings (In design)" to "Bronze (S3-first) retrofit ✅ + lightweight SC siblings ✅". Lines 60–64: change the bullet for `supercoach_teams` and `supercoach_settings` to reflect Shipped status; remove the "Run once with current season" sub-bullet (it's done).
- `docs/agents/crew/scout/charter.md` table at line 42–43: update Status column for `scout/supercoach_teams/` from "🟡 not built — Phase 2.5" to "✅ shipped (Phase 2.5)" and for `scout/supercoach_settings/` from "🟡 not built" to "✅ shipped (Phase 2.5)".
- `services/api/app/scout/supercoach_teams/README.md`: add a "Tests" section pointing to `tests/unit/api/scout/test_supercoach_teams_models.py` and `tests/integration/scout/test_supercoach_teams_response_shape.py`, plus the env-flag instruction.
- `services/api/app/scout/supercoach_settings/README.md`: same, plus a note that the integration test parameterises over `classic` and `draft` modes.
- `scripts/cron.d/jeromelu`: comments above the new lines explaining the cadence rationale (already drafted above; copy verbatim).
- `docs/operations/data-sources/supercoach/classic-teams.md` + `classic-settings.md` + `draft-settings.md`: bump the "Last refreshed" or sample-size line if the seed adds new objects. These are auto-generated by `scripts/profile_s3_json.py` — re-run that script (one command) after the seed.

**Open questions (assumptions ratified 2026-05-24):**

1. **Draft-mode in production cron** — RESOLVED: not needed in cron. Draft is roadmap-deferred and operators can `make` it on demand. Drift test still covers `mode=draft` so the path stays healthy.
2. **Fixture sample size** — RESOLVED: full payload for both (teams = 17 rows, ~3KB; settings = ~15KB). Full is the right diff target since the strict model only enforces top-level keys.
3. **One-time seed who runs it** — RESOLVED: **implementer runs the seed.** TASK-06 reframed accordingly. Requires `ADMIN_KEY` available in the implementer's environment (sourced from `/opt/jeromelu/.env` on Lightsail or equivalent locally). If unavailable, implementer blocks the task rather than improvising.

**Tasks:**

- TASK-01: Add D8 fixture + unit drift tests for `scout/supercoach_teams/`
- TASK-02: Add D8 live integration drift test for `scout/supercoach_teams/`
- TASK-03: Add D8 fixture + unit drift tests for `scout/supercoach_settings/`
- TASK-04: Add D8 live integration drift tests (classic + draft) for `scout/supercoach_settings/`
- TASK-05: Extend `scripts/scout-refresh.sh` + add cron lines for SC teams + settings
- TASK-06: One-time S3 seed + DB verification + roadmap/charter status flip + S3 profile docs refresh

---

## 2026-05-27: Change-only storage for video_metrics + channel_metrics

**Goal:** Stop appending unchanged daily snapshots to the metrics time-series. Record a new `video_metrics` / `channel_metrics` row **only when the metrics payload differs from that entity's most recent recorded snapshot**, then one-time dedup the existing history and reclaim disk. Prod evidence (2026-05-27): 70.2% of the 2.13M `video_metrics` rows are byte-identical to the prior snapshot (1,498,053 droppable); 38% of videos never changed once in 3 weeks; steady-state only ~24% of daily snapshots change. Outcome: `video_metrics` ~641 MB / 2.13M rows → ~191 MB / ~637k rows, daily growth ~37 MB → ~9 MB (~4×). `channel_metrics` gets the identical treatment for symmetry (tiny payload, negligible savings, but one pattern everywhere).

**Why this is safe — the three design calls (ratified with the human 2026-05-27):**

1. **Scope = both tables.** `video_metrics` holds the bloat; `channel_metrics` is a structural twin and gets the same helper + dedup so the siblings don't diverge.
2. **Freshness derives from the refresh run, not a per-row timestamp.** Under change-only storage the latest row's `sampled_at` means "last *changed*", not "last *checked*". We deliberately do **not** add a per-row/per-source `last_checked_at` (that would trade `video_metrics` bloat for ~120k timestamp UPDATEs/day of `sources` bloat). Instead: a successful daily refresh means every video/channel was checked that day, so "is this metric current?" is answered by the last successful refresh run (observable via the daily `cron-report` and the refresh job's `agent_runs` row). This must be documented so a future reader doesn't misread a stale `sampled_at`.
3. **Reclaim = one-time `VACUUM (FULL, ANALYZE)` on prod**, run by the human as a documented runbook step (NOT a migration — `VACUUM` cannot run inside a transaction, and it's maintenance, not schema). The dedup `DELETE` ships as migration 070 and runs everywhere via `make migrate`; only the space-return-to-OS rewrite is the manual prod step.

**Constraints:**

- **Refactor landed:** the YouTube refresh code now lives at `services/api/app/scout/youtube/refresh.py` (627 lines). `services/api/app/scout/refresh.py` is a 4-line compatibility shim (`from .youtube.refresh import *`). **All new code edits target `scout/youtube/refresh.py`.** Existing tests import via the shim (`from app.scout.refresh import ...`) and still work; **new tests import from the canonical path** `from app.scout.youtube.refresh import _metrics_changed`.
- **Equality is pinned to the existing payload builders** — do not invent a new comparison. Videos already slice to `_METRIC_FIELDS = ("views", "likes", "comments")` before insert (`youtube/refresh.py` ~line 53); channels build `{subscribers, videos, views, country, channel_published_at}` in `refresh_all_channel_stats`. `_metrics_changed` compares those already-built dicts with plain `!=` (JSONB round-trips to a `dict` with the same int/str values; `dict` equality is key-order independent).
- **The only daily-append writers to change are `refresh_all_video_stats` and `refresh_all_channel_stats`.** Leave the first-snapshot writers untouched (they have no prior row, so skip-if-unchanged is a no-op there): `refresh_channel_videos` (`youtube/refresh.py` ~line 176, new-video discovery), `recon.py` ~line 306 (channel approval discovery snapshot), and `services/api/scripts/canonicalise_handles.py` ~line 83 (one-off backfill, already guarded by `if not existing_metric`). Name them in the docstring so a future reader knows they were considered.
- **The `video_latest_metrics` / `channel_latest_metrics` views are unchanged and must keep returning the current value.** `DISTINCT ON (...) ORDER BY ... sampled_at DESC` returns the last *change*, which under change-only storage **is** the current value. This is a verification target, not a code change.
- **Velocity/breakout reads are already change-only-safe — verify, don't rewrite.** `scripts/content_report.py` `fetch_channel_velocity` / `fetch_headline` use the `JOIN LATERAL (... WHERE sampled_at < now() - interval '6 days' ORDER BY sampled_at DESC LIMIT 1)` "most-recent-row-as-of-cutoff" pattern, which returns the true value as of the cutoff regardless of gaps. `fetch_top_new_videos` reads `video_latest_metrics` (current state). No consumer does consecutive-row `LAG` velocity that would assume a row exists at an exact prior date. The implementer **confirms this by reading the file** and records the confirmation; if any query is found to assume an exact-date prior row, STOP and file a new task rather than improvising.
- META: migrations only via `make migrate`; new migration is `070_dedup_metrics_snapshots.sql`. Session-scoped staging — stage only files this work creates/modifies; the Scout-refactor diff belongs to another session and must not be swept in (`git diff --cached --stat` before commit).

**Interface:**

### New pure helper — `services/api/app/scout/youtube/refresh.py`

```python
def _metrics_changed(previous: dict | None, current: dict) -> bool:
    """True when `current` should be recorded — i.e. there is no prior
    snapshot, or the payload differs from the most recent stored one.

    `current` is the already-sliced payload (videos: _METRIC_FIELDS;
    channels: the subscribers/videos/views/country/channel_published_at
    dict). Comparison is plain dict equality, so JSONB key order and
    int/str round-tripping don't matter."""
    return previous is None or previous != current
```

### New loaders — same file

```python
def _latest_video_metrics(session: Session) -> dict[UUID, dict]:
    """source_id → its most-recent recorded metrics payload (the set the
    `video_latest_metrics` view exposes). Loaded once per refresh so the
    write loop can skip re-recording an unchanged snapshot."""
    stmt = (
        select(VideoMetric.source_id, VideoMetric.metrics)
        .distinct(VideoMetric.source_id)
        .order_by(VideoMetric.source_id, VideoMetric.sampled_at.desc())
    )
    return {row.source_id: row.metrics for row in session.execute(stmt)}

def _latest_channel_metrics(session: Session) -> dict[UUID, dict]:
    """channel_id → most-recent recorded metrics payload. Twin of the above."""
    # identical shape over ChannelMetric.channel_id / .metrics
```

`metrics` is JSONB-typed on the ORM model, so rows come back as `dict` (no manual `json.loads`). `DISTINCT ON` is Postgres-native via SQLAlchemy `.distinct(col)` and is equivalent to the `*_latest_metrics` view.

### Wiring — `refresh_all_video_stats` (and symmetric in `refresh_all_channel_stats`)

Load latest once before the batch loop; gate the existing `session.add(...)`:

```python
latest = _latest_video_metrics(session)        # before the for-batch loop
...
metric_payload = {k: entry[k] for k in _METRIC_FIELDS if k in entry}
if metric_payload:
    if _metrics_changed(latest.get(source_id), metric_payload):
        session.add(VideoMetric(... metrics=metric_payload ...))
        refreshed += 1
    else:
        unchanged += 1
```

Return dicts gain one key each: `refresh_all_video_stats` → `"videos_unchanged": unchanged`; `refresh_all_channel_stats` → `"channels_unchanged": unchanged`. These keys flow through the `recon.py` admin-refresh endpoint response body (additive, backward-compatible). The identity-field sync onto `sources` / `channels` is **unchanged** — it always runs, independent of the metric skip.

### Migration — `packages/db/migrations/070_dedup_metrics_snapshots.sql`

House-style header comment (rationale + idempotency + "VACUUM is a separate manual step, see runbook"). Two LAG-based deletes — keep every entity's first snapshot and every change, drop runs of byte-identical consecutive rows:

```sql
WITH ordered AS (
    SELECT metric_id, metrics,
           lag(metrics) OVER (PARTITION BY source_id ORDER BY sampled_at) AS prev
    FROM video_metrics
)
DELETE FROM video_metrics vm
USING ordered o
WHERE vm.metric_id = o.metric_id
  AND o.prev IS NOT NULL
  AND o.metrics = o.prev;       -- jsonb '=' is semantic / key-order independent

-- then the identical statement over channel_metrics partitioned by channel_id
```

Idempotent: after one pass, consecutive rows always differ, so re-running deletes nothing. Safe on fresh/CI/local DBs (no-op or small). Contains **no** `VACUUM`.

### Reclaim runbook — `docs/operations/metrics-dedup-runbook.md` (new)

One-time prod step after migration 070 deploys, run by the human (brief `ACCESS EXCLUSIVE` lock; schedule off-hours; 40 GB free disk covers the rewrite):

```sql
VACUUM (FULL, ANALYZE) video_metrics;
VACUUM (FULL, ANALYZE) channel_metrics;
```

Plus before/after size query (`pg_total_relation_size`), expected `video_metrics` 641 MB → ~191 MB, and a "no rollback needed — VACUUM is non-destructive" note.

**Verification strategy:**

- **TASK-07 (gating):** `make test` green including a new `TestMetricsChanged` class in `tests/unit/api/scout/test_refresh_helpers.py` (cases: `previous is None` → record; equal payload → skip; one value changed → record; key-set differs, e.g. `comments` dropped → record; reordered keys equal → skip). Implementer records in proof the read-confirmation that `content_report.py` velocity queries use the as-of-cutoff / latest-view pattern. **Deferred (post-deploy):** the admin refresh endpoint (or `/var/log/jeromelu/scout-refresh.log`) reports `videos_unchanged` ≈ 75% of `videos_total` and `videos_refreshed` ≈ 29k (not ~119k) on the next daily run.
- **TASK-08 (gating, local):** `make migrate` applies 070 against local; assert (a) **latest-state preserved** — `SELECT md5(string_agg(source_id::text || metrics::text, '' ORDER BY source_id)) FROM video_latest_metrics` is **identical before and after** the migration (same check for `channel_latest_metrics`); (b) **idempotent** — re-running the embedded dedup `SELECT` (the `ordered` CTE filtered to `prev = metrics`) returns 0 rows post-migration; (c) total row count drops. Capture before/after counts.
- **TASK-09:** runbook file exists with the exact commands, lock warning, and before/after size query; data docs + cron comment updated. **Deferred (post-deploy):** human runs the `VACUUM (FULL, ANALYZE)`; observe `video_metrics` total relation size 641 MB → ~191 MB (mirror the TASK-06 deferred-verification pattern).
- **Tiers:** unit only (pure helper). DB-backed write-path behaviour is verified end-to-end via the post-deploy refresh response, consistent with the existing convention that DB-backed refresh logic lives outside the unit tier (see `test_refresh_helpers.py` header).

**Documentation updates:**

- `services/api/app/scout/youtube/refresh.py` — module docstring + `refresh_all_video_stats` / `refresh_all_channel_stats` docstrings: change "append a row" → "append a row only when the payload differs from the latest snapshot; unchanged samples are skipped." Note the first-snapshot writers that intentionally don't skip. (TASK-07, same changeset.)
- `docs/operations/data-catalogue/video_metrics.md` + `channel_metrics.md` — document change-only write semantics and the freshness-derives-from-the-refresh-run note. (TASK-07.)
- `docs/operations/data-lineage/video_metrics.md` + `channel_metrics.md` — Writer line: "INSERTs one row per video per sample" → "INSERTs a row only when views/likes/comments change vs the latest snapshot." Add the as-of read-pattern note for velocity consumers. (TASK-07.)
- `scripts/cron.d/jeromelu` — comment on the daily video refresh (line ~26-31): "snapshots video_metrics" → "snapshots video_metrics (only rows whose metrics changed)." (TASK-07.)
- `docs/operations/metrics-dedup-runbook.md` — new runbook (TASK-09).
- Do **not** edit migrations 023/024; document the behaviour change in 070's header and the data docs.

**Open assumptions (ratified 2026-05-27):**

1. Scope both tables — RESOLVED (human chose "Both").
2. Freshness from refresh run, no `last_checked_at` column — RESOLVED (human chose "Derive from refresh run").
3. `VACUUM FULL` one-time prod reclaim — RESOLVED (human chose "VACUUM FULL one-time").
4. Scout refactor complete; canonical path `scout/youtube/refresh.py` — RESOLVED (human confirmed 2026-05-27).

**Tasks:**

- TASK-07: Skip-if-unchanged in the refresh write path (both tables) + helper unit tests + behaviour docs
- TASK-08: Migration 070 — one-time dedup of existing `video_metrics` + `channel_metrics` snapshots
- TASK-09: Prod reclaim runbook + deferred `VACUUM FULL` size verification

---

## Completed work

Completed plans are **not** archived in this file. When a plan's tasks are all done, its durable record is a run report under [`docs/build/runs/`](./runs/) (see the [index](./runs/README.md)) and the plan is removed from "Active plan" above. This document holds only active/future plans; the run reports are the system of record for what shipped.
