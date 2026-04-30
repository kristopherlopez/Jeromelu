-- 033: source video metadata + channel handle
--
-- Cheap-wins captured at zero extra YouTube API quota cost: every videos.list
-- and channels.list response we already make returns these fields, we were
-- just discarding them. Pulling them now saves us future API calls and
-- enables filtering / display use cases without schema friction later.
--
-- sources:
--   description       — full video description (chapter timestamps live here)
--   thumbnail_url     — best available thumbnail (used by UI)
--   duration_seconds  — video length in seconds (constant per video)
--   is_short          — generated from duration_seconds < 60; YouTube Shorts
--                       are lower-information content and frequently filtered
--                       out of analysis
--
-- channels:
--   handle            — the @handle (customUrl) — useful for UI links and as
--                       a fallback resolution path when external_id is a
--                       handle rather than UC id (cf. NRL Physio incident)

ALTER TABLE sources
    ADD COLUMN IF NOT EXISTS description       TEXT,
    ADD COLUMN IF NOT EXISTS thumbnail_url     TEXT,
    ADD COLUMN IF NOT EXISTS duration_seconds  INTEGER,
    ADD COLUMN IF NOT EXISTS is_short          BOOLEAN
        GENERATED ALWAYS AS (
            duration_seconds IS NOT NULL AND duration_seconds < 60
        ) STORED;

CREATE INDEX IF NOT EXISTS idx_sources_is_short
    ON sources (is_short) WHERE is_short = true;
CREATE INDEX IF NOT EXISTS idx_sources_duration
    ON sources (duration_seconds) WHERE duration_seconds IS NOT NULL;

COMMENT ON COLUMN sources.description IS
    'Video / podcast / article description as published. May contain '
    'chapter timestamps, links, etc. Updated when YouTube content changes.';
COMMENT ON COLUMN sources.thumbnail_url IS
    'Best available thumbnail URL (YouTube high/maxres, podcast cover art, '
    'article OG image). Highest-resolution available at capture time.';
COMMENT ON COLUMN sources.duration_seconds IS
    'Length in seconds. Constant for a given video; refreshed on stats sync.';
COMMENT ON COLUMN sources.is_short IS
    'True when duration_seconds < 60 (YouTube Shorts). Generated column.';

ALTER TABLE channels
    ADD COLUMN IF NOT EXISTS handle TEXT;

CREATE INDEX IF NOT EXISTS idx_channels_handle
    ON channels (handle) WHERE handle IS NOT NULL;

COMMENT ON COLUMN channels.handle IS
    'Platform handle (YouTube @customUrl, Twitter @handle, etc.). Useful '
    'for UI links and as a fallback when external_id is a handle rather '
    'than the canonical platform id.';
