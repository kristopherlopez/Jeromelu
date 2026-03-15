-- channels: registry of content sources (YouTube, podcasts, websites, etc.)
CREATE TABLE channels (
    channel_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug TEXT NOT NULL UNIQUE,
    platform VARCHAR(20) NOT NULL
        CHECK (platform IN ('youtube', 'podcast', 'website', 'twitter', 'instagram')),
    external_id TEXT,
    name TEXT NOT NULL,
    url TEXT,
    description TEXT,
    quality_rating INTEGER DEFAULT 5,
    tags TEXT[] DEFAULT '{}',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    last_polled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (platform, external_id)
);

CREATE INDEX idx_channels_platform ON channels (platform);
CREATE INDEX idx_channels_active ON channels (active);
