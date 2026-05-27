# Change-only storage for video_metrics + channel_metrics

**Date:** 2026-05-27 · **Status:** 🟢 Shipped (prod deduped + reclaimed; write-path payoff confirmed by tonight's cron) · **Plan:** PLAN.md § 2026-05-27 (removed from Active on completion) · **Tasks:** TASK-07 → TASK-09

**TL;DR** — Stop appending unchanged daily snapshots to the metrics time-series. Prod evidence (2026-05-27): 70.2% of the 2.13M `video_metrics` rows are byte-identical to the prior snapshot; steady-state only ~24% of daily samples change. The fix: skip-if-unchanged in the daily refresh (TASK-07), a one-time dedup migration (TASK-08), and a `VACUUM FULL` reclaim runbook (TASK-09). **Shipped to prod 2026-05-27: `video_metrics` 641 MB → 171 MB** (2,135,406 → 637,353 rows; ~470 MB reclaimed), daily growth ~37 MB → ~9 MB. Write-path skip is live; the steady-state ~76 %-unchanged ratio confirms on the next daily refresh.

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

### TASK-08 — Migration 070: one-time dedup of existing snapshots (`61fa974`)
Added `packages/db/migrations/070_dedup_metrics_snapshots.sql` — two `BEGIN`/`COMMIT`-wrapped LAG-window deletes (one per table) that keep every entity's first snapshot + every change and drop runs of byte-identical consecutive rows (`o.prev IS NOT NULL AND o.metrics = o.prev`, jsonb equality). House-style header explaining the 70.2% finding, idempotency, and the deferral of disk reclaim to the runbook (no `VACUUM` — can't run in a txn). Both `video_metrics` and `channel_metrics` covered.

**Verified (local, `make migrate` → applied 070):**
- Before: `video_metrics` 5485 / `channel_metrics` 26. After: **4189 / 26** (the local seed's within-day re-snapshots collapsed; the small channel set had no consecutive dupes).
- **Latest-state preserved:** `video_latest_metrics` md5 `98a633438397972b53911b7d048ae745` and `channel_latest_metrics` md5 `26e8ef0eed3b7ac57e7c1c75d07f877b` — **byte-identical before and after**.
- **Idempotent:** residual consecutive-duplicate probe = **0** for both tables; `070_dedup_metrics_snapshots.sql` tracked in `schema_migrations`, so re-run is a no-op.
- adversarial-reviewer: **PASS WITH CONCERNS** (concerns were the pending commit + this proof recording; reviewer independently re-ran the residual probe → 0/0 and confirmed the latest views return one row per entity: 2094 video / 14 channel).

### TASK-09 — Prod reclaim runbook (doc deliverable) (`a8c9ebf`) · prod VACUUM deferred
Wrote `docs/operations/metrics-dedup-runbook.md` (frontmatter-consistent with `iac-runbook.md`): purpose, preconditions (070 applied on prod, off-hours, disk headroom), the exact `VACUUM (FULL, ANALYZE) video_metrics; … channel_metrics;` commands with a one-at-a-time / not-in-a-txn note, the `ACCESS EXCLUSIVE` lock warning, the `pg_total_relation_size` before/after query, expected sizes (641 MB → ~191 MB, ~450 MB returned), a no-rollback note, and the on-box `ssh jeromelu-prod` + `docker exec … psql` connection (the box isn't reachable externally). Linked it from `docs/operations/data-catalogue/video_metrics.md`.

**Verified:** adversarial-reviewer **PASS WITH CONCERNS** — independently cross-checked the commands, the `pg_total_relation_size` query, the cron/backup windows against `scripts/cron.d/jeromelu` (exact match), the connection method against `docker-compose.yml`, the precondition SQL against `migrate.sh`, and the relative link path (resolves). Concerns: the "58 GB" disk total isn't sourced in the inventory doc (but the runbook cites live `df -h /`, the authoritative source; headroom conclusion sound) and a pre-existing stale RDS row in `aws-resource-inventory.md` (out of scope — flagged, not fixed).

**Executed on prod 2026-05-27** (with human go-ahead). Context: the prod deploy had been stuck behind a GitHub Actions billing block since 05-24 (resolved by making the repo public), which is why the box sat 19 commits behind master. Once CI ran, the box was brought to current master (`83ad808 chore(deploy): rebuild api+web from master`, api+web images rebuilt) and migration 070 was applied via `migrate.sh` — so the dedup `DELETE` had already run when this session checked. The implementer then ran the `VACUUM (FULL, ANALYZE)` (the runbook's reclaim step):

- **Code live:** the running `jeromelu-api` container (rebuilt, 58 min old) contains `_metrics_changed` — skip-if-unchanged is in effect, so the dedup sticks.
- **Dedup verified before VACUUM:** `video_metrics` 2,135,406 → **637,353** rows — *exactly* the predicted survivor count (120,025 first-snapshots + 517,328 changes). `video_latest_metrics` still returns **120,025** rows (no video dropped) and `channel_latest_metrics` **180** (all channels retained). Residual consecutive-dupe probe **0/0**.
- **VACUUM (FULL, ANALYZE)** on both tables completed in **~4 s** (13:36:07→13:36:11 UTC, off-peak): **`video_metrics` 641 MB → 171 MB** (heap 98 MB + idx 73 MB; ~470 MB / ~73 % returned to the OS), `channel_metrics` 2016 kB → 1488 kB.
- **Post-VACUUM integrity:** `video_latest_md5` `b2e926781d0f69dae4d32f123dd1ab2c` and `channel_latest_md5` `6309feeacab2c5233526142264e552f7` — byte-identical before/after the VACUUM; counts unchanged. No data altered.

---

## Outstanding
- ☐ **Write-path payoff confirmation (passive, automatic).** Skip-if-unchanged is live; tonight's 23:15 UTC video refresh (and the Tuesday cron-report email) will show `videos_refreshed` ≈ 24 % of `videos_total` and `videos_unchanged` the remaining ~76 % in `/var/log/jeromelu/scout-refresh.log`. Not blocking — closes itself on the next cron run. No manual trigger run (would duplicate the cron at ~720 quota units for no extra signal).
- ✅ **Resolved — migration 070 + dedup + VACUUM on prod** (see above).
- ⚠️ **PLAN.md staleness (now moot):** the plan's Constraints described `scout/refresh.py` as a live shim; the Scout refactor removed it. The plan is removed from Active on this completion, so the staleness is retired.

## Commits
`fd8e0a3` (TASK-07) · `61fa974` (TASK-08) · `a8c9ebf` (TASK-09 doc deliverable). Prod deploy `83ad808` (code + migration 070); VACUUM run via `docker exec` per the runbook (maintenance, not a commit). All code on `master`.
