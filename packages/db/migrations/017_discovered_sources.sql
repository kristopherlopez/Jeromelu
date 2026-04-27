-- 017: discovered_sources — Scout's candidate inbox
--
-- Scout (the source-discovery agent) writes here as it hunts the web for
-- new NRL channels and videos worth onboarding. Humans approve or reject
-- via the admin review queue. Approval promotes a row into the canonical
-- channels / sources tables.
--
-- Distinct from `sources` (which is for ingested content) so unapproved
-- noise doesn't pollute the main pipeline.

CREATE TABLE discovered_sources (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind                 TEXT NOT NULL,           -- 'channel' | 'video'
    platform             TEXT NOT NULL DEFAULT 'youtube',
    external_id          TEXT NOT NULL,           -- youtube channel_id or video_id
    url                  TEXT NOT NULL,
    title                TEXT NOT NULL,
    description          TEXT,
    channel_external_id  TEXT,                    -- for videos: parent channel
    content_categories   TEXT[] DEFAULT '{}',     -- match | analysis | news | injury | tactical | opinion | player-content | classic | rules-officiating | supercoach | nrlw | origin | international | junior
    score                NUMERIC,                 -- agent's qualitative score 0..1
    score_reasons        JSONB DEFAULT '[]',      -- ["Australian focus", "10k+ subs", "Weekly uploads"]
    metadata_json        JSONB DEFAULT '{}',      -- subs, view_count, published_at, duration, etc.
    discovered_via       TEXT NOT NULL,           -- query string OR 'related-to:<channel_id>' OR 'manual'
    discovered_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    status               TEXT NOT NULL DEFAULT 'pending',
    reviewed_at          TIMESTAMPTZ,
    reviewed_by          TEXT,
    reviewed_note        TEXT,
    promoted_channel_id  UUID REFERENCES channels(channel_id),
    run_id               TEXT,                    -- groups all candidates from one Scout run

    CONSTRAINT ck_discovered_kind   CHECK (kind IN ('channel', 'video')),
    CONSTRAINT ck_discovered_status CHECK (status IN ('pending', 'approved', 'rejected', 'snoozed', 'duplicate')),
    UNIQUE (platform, kind, external_id)
);

CREATE INDEX idx_discovered_status ON discovered_sources (status);
CREATE INDEX idx_discovered_kind   ON discovered_sources (kind);
CREATE INDEX idx_discovered_run    ON discovered_sources (run_id);
CREATE INDEX idx_discovered_at     ON discovered_sources (discovered_at DESC);
