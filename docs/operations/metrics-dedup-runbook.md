---
tags: [area/operations]
---

# Metrics dedup — disk reclaim runbook

One-time prod maintenance to return disk to the OS after the change-only-storage
switch. Pairs with migration `070_dedup_metrics_snapshots.sql` (the logical
dedup) and the skip-if-unchanged write path in
`services/api/app/scout/youtube/refresh.py`. Background + evidence:
[PLAN.md § 2026-05-27](../build/PLAN.md) and the
[run report](../build/runs/2026-05-27-change-only-metrics-storage.md).

## Why this is a separate step

Migration 070 **deletes** ~70% of `video_metrics` rows, but Postgres returns the
freed space to the table's own freelist, **not to the OS** — the files stay
~641 MB and the space is only reused by future inserts. Under change-only
storage future growth is slow (~9 MB/day vs ~37 MB/day), so the bloat would take
months to be reabsorbed. To shrink the files now, run `VACUUM (FULL)`, which
rewrites the table + all its indexes compactly.

`VACUUM` cannot run inside a transaction, so it is **not** part of the
migration — it's this manual step.

## Preconditions

- Migration `070_dedup_metrics_snapshots.sql` has been **applied on prod** (the
  dedup `DELETE` has run). Check: `SELECT version FROM schema_migrations WHERE version = '070_dedup_metrics_snapshots.sql';` returns a row.
- Run **off-hours** — `VACUUM FULL` takes an `ACCESS EXCLUSIVE` lock (see below).
  Avoid the daily refresh windows (`23:00`/`23:15` UTC) and the nightly backup
  (`16:30` UTC).
- Disk headroom: `VACUUM FULL` writes a full new copy before dropping the old.
  Confirmed ample — the box has ~40 GB free of 58 GB (`df -h /`), and the result
  is ~191 MB.

## ⚠️ Lock warning

`VACUUM (FULL)` holds an **`ACCESS EXCLUSIVE`** lock for the whole rewrite —
the table is **unavailable for both reads and writes** during it. For the
~191 MB post-dedup `video_metrics` result this is seconds to low minutes;
`channel_metrics` is trivial (~2 MB). Anything touching `video_metrics` /
`video_latest_metrics` (the wiki cards, content-report velocity, admin
endpoints) blocks until it finishes. Do it off-hours and expect a brief stall,
not an outage.

## Procedure

Connect on the box (it can't be reached from outside; SSH in and exec into the
postgres container):

```bash
ssh jeromelu-prod
docker exec -it jeromelu-postgres psql -U jeromelu_admin -d jeromelu
```

**1. Capture before-size:**

```sql
SELECT pg_size_pretty(pg_total_relation_size('video_metrics'))   AS video,
       pg_size_pretty(pg_total_relation_size('channel_metrics')) AS channel;
-- expected (pre-reclaim): video ≈ 641 MB, channel ≈ 2 MB
```

**2. Reclaim** (each statement runs outside a txn — run them one at a time, not
wrapped in `BEGIN`):

```sql
VACUUM (FULL, ANALYZE) video_metrics;
VACUUM (FULL, ANALYZE) channel_metrics;
```

`ANALYZE` refreshes planner stats after the rewrite (row estimates changed a
lot). `VACUUM FULL` rebuilds the indexes too, so no separate `REINDEX` is
needed.

**3. Capture after-size** (same query as step 1):

```sql
SELECT pg_size_pretty(pg_total_relation_size('video_metrics'))   AS video,
       pg_size_pretty(pg_total_relation_size('channel_metrics')) AS channel;
-- expected (post-reclaim): video ≈ 191 MB (~70% reclaimed, ~450 MB returned),
-- channel ≈ 1–2 MB
```

## Rollback

None needed — `VACUUM` is non-destructive (it rewrites the same rows compactly;
it does not change data). If interrupted, the table is left in its prior state
and the command can simply be re-run.

## Verification

The reclaim is done when the step-3 `video_metrics` total relation size is
~191 MB (down from ~641 MB). Record the before/after output in the
[run report](../build/runs/2026-05-27-change-only-metrics-storage.md) to close
TASK-09.
