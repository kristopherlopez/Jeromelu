-- 025: channels.logo_url — stable per-channel avatar / cover image URL
--
-- YouTube's channels.list returns snippet.thumbnails (default/medium/high).
-- Apple/Spotify podcasts have cover art. Twitter avatars exist. All are
-- stable per-channel attributes, not popularity metrics, so they belong on
-- the canonical channels record rather than channel_metrics.
--
-- We store ONE URL — typically the highest-resolution available. UI scales
-- with CSS as needed.

ALTER TABLE channels ADD COLUMN IF NOT EXISTS logo_url TEXT;

COMMENT ON COLUMN channels.logo_url IS
    'Channel avatar / cover image URL (YouTube thumbnail, podcast cover art, '
    'Twitter avatar, etc.). Highest-resolution available at capture time.';
