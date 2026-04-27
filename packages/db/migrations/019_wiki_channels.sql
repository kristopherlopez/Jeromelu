-- 019: Channel wiki pages
--
-- Wiki pages can now describe a channel (the outlet — SC Playbook YouTube,
-- NRL Physio Twitter) in addition to an entity (the person/voice). Channels
-- have authoritative records in the channels table; advisors (people behind
-- the channels) are deferred until speaker diarisation lands.
--
-- - wiki_pages.entity_id becomes nullable
-- - new wiki_pages.channel_id FK to channels(channel_id)
-- - exactly-one-of constraint on subject (entity_id XOR channel_id)
-- - 'channel' added to ck_wiki_page_type
-- - delete legacy seeded "advisor" entities (they were really channels)
-- - backfill one channel wiki page per channels row

-- ---------------------------------------------------------------------------
-- 1. Subject expansion
-- ---------------------------------------------------------------------------
ALTER TABLE wiki_pages ALTER COLUMN entity_id DROP NOT NULL;

ALTER TABLE wiki_pages
  ADD COLUMN IF NOT EXISTS channel_id UUID REFERENCES channels(channel_id);

CREATE INDEX IF NOT EXISTS idx_wiki_pages_channel ON wiki_pages(channel_id);

ALTER TABLE wiki_pages DROP CONSTRAINT IF EXISTS ck_wiki_page_type;
ALTER TABLE wiki_pages ADD CONSTRAINT ck_wiki_page_type
  CHECK (page_type IN ('player', 'team', 'advisor', 'round', 'channel'));

ALTER TABLE wiki_pages DROP CONSTRAINT IF EXISTS ck_wiki_page_subject;
ALTER TABLE wiki_pages ADD CONSTRAINT ck_wiki_page_subject CHECK (
    (entity_id IS NOT NULL AND channel_id IS NULL)
    OR (entity_id IS NULL AND channel_id IS NOT NULL)
);

-- ---------------------------------------------------------------------------
-- 2. Remove legacy seeded "advisor" entities + their wiki pages.
--    Verified pre-migration: zero references in claims/quotes/predictions.
--    They were really channels mislabelled before the channels table existed.
-- ---------------------------------------------------------------------------
DELETE FROM wiki_pages
WHERE entity_id IN (
    'a0000001-0000-0000-0000-000000000001',
    'a0000001-0000-0000-0000-000000000002'
);

DELETE FROM entities
WHERE entity_id IN (
    'a0000001-0000-0000-0000-000000000001',
    'a0000001-0000-0000-0000-000000000002'
);

-- ---------------------------------------------------------------------------
-- 3. Backfill — one channel wiki page per channels row.
--    Idempotent: skips channels that already have a wiki page.
-- ---------------------------------------------------------------------------
INSERT INTO wiki_pages (
    entity_id, channel_id, page_type, slug, title, content, summary, metadata_json, status
)
SELECT
    NULL,
    c.channel_id,
    'channel',
    c.slug,
    c.name,
    '## About' || E'\n\n' || COALESCE(c.description, '') || E'\n\n' ||
    '## Recent Sources' || E'\n\n_None yet._' || E'\n\n' ||
    '## Coverage' || E'\n\nTags: ' || COALESCE(array_to_string(c.tags, ', '), '_(none)_') || E'\n\n' ||
    '## Hosts' || E'\n\n_Hosts will be linked once advisor pages exist._',
    LEFT(COALESCE(c.description, c.name), 280),
    jsonb_build_object(
        'platform', c.platform,
        'url', c.url,
        'quality_rating', c.quality_rating,
        'tags', to_jsonb(c.tags)
    ),
    'stub'
FROM channels c
WHERE NOT EXISTS (
    SELECT 1 FROM wiki_pages wp WHERE wp.channel_id = c.channel_id
);
