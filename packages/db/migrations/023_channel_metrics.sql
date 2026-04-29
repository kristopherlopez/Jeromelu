-- 023: channel_metrics — time-series popularity tracking per channel
--
-- Channels are multi-platform (youtube, podcast, twitter, instagram, website),
-- and each platform has its own popularity shape — subs/views/videos for
-- YouTube, followers/tweets for X, ratings/rankings for podcasts. Cramming all
-- of those into typed columns on `channels` would either bloat the table with
-- mostly-NULL columns or stretch single column meanings across platforms.
--
-- Instead, keep `channels` clean (identity, not state) and put popularity in
-- this dedicated time-series table:
--   - one row per (channel, sampled_at)
--   - JSONB `metrics` lets each platform carry its own shape
--   - sampled_at supports trend analysis (sub growth over time)
--   - the channel_latest_metrics view gives the "current state" common case

CREATE TABLE channel_metrics (
    metric_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id  UUID NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
    platform    TEXT NOT NULL,
    sampled_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    source      TEXT NOT NULL,           -- 'youtube_api' | 'apple_podcasts' | 'manual' | ...
    metrics     JSONB NOT NULL DEFAULT '{}',

    UNIQUE (channel_id, sampled_at)
);

CREATE INDEX idx_channel_metrics_channel_time
    ON channel_metrics (channel_id, sampled_at DESC);
CREATE INDEX idx_channel_metrics_platform_time
    ON channel_metrics (platform, sampled_at DESC);
CREATE INDEX idx_channel_metrics_sampled_at
    ON channel_metrics (sampled_at DESC);

-- Latest metrics per channel — most queries (wiki cards, ranking) only want
-- "the current state", not the history.
CREATE VIEW channel_latest_metrics AS
SELECT DISTINCT ON (channel_id)
    channel_id,
    platform,
    sampled_at,
    source,
    metrics
FROM channel_metrics
ORDER BY channel_id, sampled_at DESC;

COMMENT ON TABLE channel_metrics IS
    'Time-series popularity metrics per channel. Multi-platform via JSONB metrics column. '
    'See channel_latest_metrics view for the latest-only common case.';

-- ---------------------------------------------------------------------------
-- Backfill — one row per already-approved YouTube channel using the metadata
-- captured at discovery time. Normalises the 'subs' / 'subscribers' key
-- inconsistency that crept in at agent-prompt level.
-- ---------------------------------------------------------------------------
INSERT INTO channel_metrics (channel_id, platform, sampled_at, source, metrics)
SELECT
    ds.promoted_channel_id,
    ds.platform,
    COALESCE(ds.reviewed_at, ds.discovered_at),
    'youtube_api',
    jsonb_strip_nulls(jsonb_build_object(
        -- Normalise on 'subscribers' (matches the YouTube API field name).
        'subscribers',
            COALESCE(
                (ds.metadata_json->>'subscribers')::int,
                (ds.metadata_json->>'subs')::int
            ),
        'videos',          (ds.metadata_json->>'video_count')::int,
        'views',           (ds.metadata_json->>'view_count')::bigint,
        'country',         ds.metadata_json->>'country',
        'channel_published_at', ds.metadata_json->>'published_at'
    ))
FROM discovered_sources ds
WHERE ds.status = 'approved'
  AND ds.platform = 'youtube'
  AND ds.kind = 'channel'
  AND ds.promoted_channel_id IS NOT NULL
  AND ds.metadata_json <> '{}'::jsonb;
