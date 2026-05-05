-- 051: indexes to support paginated /admin/pipeline/items at 100k+ scale.
--
-- After Scout's fleet backfill the sources table has ~100k rows. The admin
-- dashboard's prior all-rows endpoint (/admin/pipeline) is being replaced
-- by a paginated one (GET /admin/pipeline/items?...&limit&offset). Without
-- supporting indexes a 50-row paginated query at 100k+ rows still does a
-- full table scan plus an in-memory sort.
--
-- Two indexes:
--   1. (published_at DESC NULLS LAST) — covers the default global sort
--      (newest first) and ORDER BY ... LIMIT 50 reads the first 50 rows
--      from the index without scanning the table.
--   2. (channel_id, published_at DESC NULLS LAST) — covers per-channel
--      filter + sort, the natural "show me everything for Bloke in a Bar
--      newest first" query. Also useful for /admin/scout/channel-coverage's
--      tracked-videos subquery once it's predicate-pushed.
--
-- Both are pure btree indexes on already-existing columns. Idempotent
-- via IF NOT EXISTS so re-running the migration is safe.

BEGIN;

CREATE INDEX IF NOT EXISTS idx_sources_published_at_desc
    ON sources (published_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_sources_channel_published
    ON sources (channel_id, published_at DESC NULLS LAST);

COMMIT;
