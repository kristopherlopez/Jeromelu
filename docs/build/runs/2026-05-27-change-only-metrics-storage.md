# Change-only storage for video_metrics + channel_metrics

**Date:** 2026-05-27 · **Status:** 🟡 In progress (TASK-07 shipped; TASK-08, TASK-09 open) · **Plan:** [PLAN.md § 2026-05-27](../PLAN.md) · **Tasks:** TASK-07 → TASK-09

**TL;DR** — Stop appending unchanged daily snapshots to the metrics time-series. Prod evidence (2026-05-27): 70.2% of the 2.13M `video_metrics` rows are byte-identical to the prior snapshot; steady-state only ~24% of daily samples change. The fix: skip-if-unchanged in the daily refresh (TASK-07, done), a one-time dedup migration (TASK-08), and a `VACUUM FULL` reclaim runbook (TASK-09). Target: `video_metrics` ~641 MB → ~191 MB, daily growth ~37 MB → ~9 MB.

---

## What was completed

### TASK-07 — Skip-if-unchanged in the refresh write path (both tables) (`fd8e0a3`)
Added the pure predicate `_metrics_changed(previous, current)` (`return previous is None or previous != current`) and two loaders `_latest_video_metrics` / `_latest_channel_metrics` (Postgres `DISTINCT ON` over the ORM model, ordered `sampled_at DESC`, returning `{id: metrics_dict}` — equivalent to the `*_latest_metrics` views; loaded once per run). Wired both into `refresh_all_video_stats` and `refresh_all_channel_stats` in `services/api/app/scout/youtube/refresh.py`: the `session.add(...)` is now gated on `_metrics_changed(latest.get(id), metric_payload)`, with `videos_unchanged` / `channels_unchanged` counters added to the return dicts (including the empty-input early returns). The identity-field sync onto `sources` / `channels` is unchanged — it always runs, independent of the metric skip. First-snapshot writers (`refresh_channel_videos`, the channel-approval snapshot in `routers/recon.py`, the `canonicalise_handles` backfill) are intentionally left unconditional — they have no prior row to compare.

Added `class TestMetricsChanged` to `tests/unit/api/scout/test_refresh_helpers.py` (imports from the canonical `app.scout.youtube.refresh`): None→record, equal→skip, changed→record, key-set-differs→record, reordered-keys→skip, plus a channel-shape case. Updated the module + both function docstrings, the four data docs (catalogue + lineage for both tables) with change-only semantics + the freshness-derives-from-the-refresh-run note + the as-of-cutoff read note, and the daily-video-refresh comment in `scripts/cron.d/jeromelu`.

**Decision recorded:** under change-only storage the latest row's `sampled_at` means *last changed*, not *last checked*. Per the plan's ratified design, freshness derives from the last successful daily refresh run (cron-report / the refresh job's `agent_runs` row) — **no** per-row `last_checked_at` column (that would trade `video_metrics` bloat for ~120k `sources` UPDATEs/day).

**Verified:**
- `pytest tests/unit/api/scout/test_refresh_helpers.py -q` → **22 passed** (6 new + 16 existing). Full unit suite → **312 passed**.
- Canonical-path import resolves: `from app.scout.youtube.refresh import _metrics_changed, _latest_video_metrics, _latest_channel_metrics` (the `scout/refresh.py` shim was removed by the concurrent Scout refactor — canonical path is now mandatory).
- **content_report.py velocity reads confirmed change-only-safe, no rewrite needed** (plan step 6): `fetch_headline` (lines ~101-111) and `fetch_channel_velocity` (~148-158) both use `WHERE sampled_at < now() - interval '6 days' ORDER BY sampled_at DESC LIMIT 1` (as-of-cutoff, gap-safe); `fetch_top_new_videos` (~126) reads the `video_latest_metrics` view. No consecutive-row `LAG` velocity exists.
- Diff scope: exactly 7 files (`youtube/refresh.py`, the test, 4 data docs, the cron file). `git diff --cached --stat` confirmed no other-session files staged.
- **adversarial-reviewer: PASS WITH CONCERNS** — both non-blocking (empty TASKS.md proof-notes placeholder → satisfied by this run-report entry per the ritual; PLAN.md's "shim still exists" wording now stale → see Outstanding).

**Deferred (post-deploy):** the next daily refresh response / `scout-refresh.log` should show `videos_unchanged` ≈ 75% of `videos_total` and `videos_refreshed` an order of magnitude below the old ~119k. Record when observable.

---

## Outstanding
- ☐ **TASK-08** — migration `070_dedup_metrics_snapshots.sql` (one-time dedup of existing rows, both tables) + local before/after proof.
- ☐ **TASK-09** — `docs/operations/metrics-dedup-runbook.md` + deferred prod `VACUUM (FULL, ANALYZE)` size verification (641 MB → ~191 MB).
- ☐ **Deferred TASK-07 verification** — post-deploy `videos_unchanged` ratio in the daily refresh.
- ⚠️ **PLAN.md staleness (minor):** the plan's Constraints describe `scout/refresh.py` as a live 4-line shim, but the concurrent Scout refactor has since *removed* it. Harmless to TASK-07/08/09 (all target the canonical path); the plan section is removed when the plan completes.

## Commits
`fd8e0a3` (TASK-07). On `master`.
