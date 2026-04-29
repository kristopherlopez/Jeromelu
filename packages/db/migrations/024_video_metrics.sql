-- 024: video_metrics — time-series popularity tracking per video
--
-- Same shape as channel_metrics (see migration 023): identity stays in the
-- canonical table (sources), state goes in a dedicated time-series table.
--
-- Per-video popularity (views, likes, comments) changes constantly. Storing
-- it as columns on `sources` would lose history; storing it as JSONB on
-- `sources` would still lose history. A separate time-series table lets us
-- compute view-velocity, identify breakouts, and rank "what blew up this
-- week" without losing the prior weeks of data.
--
-- Sampling cadence: weekly via the admin refresh endpoint, plus a one-off
-- snapshot at video discovery time (when a channel is approved and Scout
-- enumerates its uploads).

CREATE TABLE video_metrics (
    metric_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id   UUID NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    sampled_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    source      TEXT NOT NULL,           -- 'youtube_api' | 'manual' | ...
    metrics     JSONB NOT NULL DEFAULT '{}',

    UNIQUE (source_id, sampled_at)
);

CREATE INDEX idx_video_metrics_source_time
    ON video_metrics (source_id, sampled_at DESC);
CREATE INDEX idx_video_metrics_sampled_at
    ON video_metrics (sampled_at DESC);

-- Latest metrics per video — most queries (influence ranking, wiki cards)
-- only want "the current state".
CREATE VIEW video_latest_metrics AS
SELECT DISTINCT ON (source_id)
    source_id,
    sampled_at,
    source,
    metrics
FROM video_metrics
ORDER BY source_id, sampled_at DESC;

COMMENT ON TABLE video_metrics IS
    'Time-series popularity metrics per video (sources row). YouTube uses '
    '{views, likes, comments, duration_seconds}. See video_latest_metrics '
    'view for the latest-only common case.';
