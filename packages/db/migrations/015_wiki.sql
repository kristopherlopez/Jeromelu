-- 015: Wiki pages and revision history
--
-- Adds a wiki layer for browsable, prose-dominant, agent-maintained
-- entity pages with interlinked markdown content and revision tracking.

-- ---------------------------------------------------------------------------
-- 1. Extend entity_type to include 'advisor' and 'round'
-- ---------------------------------------------------------------------------
ALTER TABLE entities DROP CONSTRAINT IF EXISTS ck_entity_type;
ALTER TABLE entities DROP CONSTRAINT IF EXISTS entities_entity_type_check;
ALTER TABLE entities ADD CONSTRAINT ck_entity_type
  CHECK (entity_type IN ('player', 'team', 'expert', 'advisor', 'matchup', 'round'));

-- ---------------------------------------------------------------------------
-- 2. Add slug column to entities
-- ---------------------------------------------------------------------------
ALTER TABLE entities ADD COLUMN IF NOT EXISTS slug TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_entities_slug ON entities(slug) WHERE slug IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 3. Wiki pages
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wiki_pages (
    page_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID NOT NULL REFERENCES entities(entity_id),
    page_type       TEXT NOT NULL,
    slug            TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT '',
    summary         TEXT,
    metadata_json   JSONB NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'stub',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_wiki_page_type CHECK (
        page_type IN ('player', 'team', 'advisor', 'round')
    ),
    CONSTRAINT ck_wiki_status CHECK (
        status IN ('stub', 'draft', 'published')
    )
);

CREATE INDEX IF NOT EXISTS idx_wiki_pages_type    ON wiki_pages(page_type);
CREATE INDEX IF NOT EXISTS idx_wiki_pages_slug    ON wiki_pages(slug);
CREATE INDEX IF NOT EXISTS idx_wiki_pages_entity  ON wiki_pages(entity_id);
CREATE INDEX IF NOT EXISTS idx_wiki_pages_updated ON wiki_pages(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_wiki_pages_status  ON wiki_pages(status);

-- ---------------------------------------------------------------------------
-- 4. Wiki revisions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wiki_revisions (
    revision_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id         UUID NOT NULL REFERENCES wiki_pages(page_id) ON DELETE CASCADE,
    section_heading TEXT,
    summary         TEXT NOT NULL,
    content_snapshot TEXT,
    source_trigger  TEXT,
    source_id       UUID REFERENCES sources(source_id),
    metadata_json   JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wiki_revisions_page    ON wiki_revisions(page_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_wiki_revisions_created ON wiki_revisions(created_at DESC);
