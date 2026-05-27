-- 070: dedup video_metrics + channel_metrics — switch to change-only storage
--
-- The metrics tables are time-series, but most daily samples are byte-identical
-- to the day before (a long tail of old videos/channels whose popularity never
-- moves). Prod evidence (2026-05-27): 70.2% of the 2.13M video_metrics rows
-- are identical to that video's previous snapshot; 38% of videos never changed
-- once in three weeks. Going forward the daily refresh records a row only when
-- the payload changed (see app/scout/youtube/refresh.py _metrics_changed); this
-- migration removes the redundancy that already accumulated.
--
-- Rule: keep every entity's FIRST snapshot and every CHANGE; drop runs of
-- byte-identical consecutive rows (ordered by sampled_at). Implemented with a
-- LAG window per source_id / channel_id — a row is droppable iff it equals the
-- immediately-preceding row for the same entity.
--
-- Latest-state is preserved: the last surviving row per entity is still the
-- most recent distinct value, so video_latest_metrics / channel_latest_metrics
-- return exactly what they did before.
--
-- Idempotent: after one pass consecutive rows always differ, so re-running
-- deletes nothing. Safe on fresh/CI/local DBs (no-op or small).
--
-- NOTE: this reclaims logical rows but NOT disk — Postgres returns the freed
-- space to the table's freelist, not the OS. To shrink the files on prod, run
-- the one-time VACUUM (FULL, ANALYZE) documented in
-- docs/operations/metrics-dedup-runbook.md. VACUUM cannot run inside a
-- transaction, so it is deliberately NOT part of this migration.

BEGIN;

-- video_metrics
WITH ordered AS (
    SELECT metric_id,
           metrics,
           lag(metrics) OVER (PARTITION BY source_id ORDER BY sampled_at) AS prev
    FROM video_metrics
)
DELETE FROM video_metrics vm
USING ordered o
WHERE vm.metric_id = o.metric_id
  AND o.prev IS NOT NULL
  AND o.metrics = o.prev;        -- jsonb '=' is semantic / key-order independent

-- channel_metrics (sibling table, identical rule partitioned by channel_id)
WITH ordered AS (
    SELECT metric_id,
           metrics,
           lag(metrics) OVER (PARTITION BY channel_id ORDER BY sampled_at) AS prev
    FROM channel_metrics
)
DELETE FROM channel_metrics cm
USING ordered o
WHERE cm.metric_id = o.metric_id
  AND o.prev IS NOT NULL
  AND o.metrics = o.prev;

COMMIT;
