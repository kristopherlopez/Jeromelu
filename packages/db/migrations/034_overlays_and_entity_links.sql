-- 034: source overlays + match/venue entity links + entity_type cleanup
--
-- This migration is the schema-side of an alignment pass against
-- docs/operations/data-catalogue.md. Three changes bundled because they
-- form one coherent reshape: identity gets two more "noun" types (match,
-- venue), the structured-world rows that back those nouns gain entity_id
-- columns, and source_documents gain three overlay layers above
-- source_chunks.
--
-- 1. entity_type: drop 'matchup', add 'match' and 'venue'.
--    'matchup' was the placeholder for "this is a discussable game".
--    Replaced by 'match' so claims/predictions/wiki can target a specific
--    fixture row in `matches`. 'venue' lets us claim about grounds
--    ("Suncorp under lights"). Existing rows with entity_type='matchup'
--    are migrated to 'match' before the constraint is swapped.
--
-- 2. matches.entity_id, venues.entity_id.
--    Same pattern as teams.entity_id — nullable, UNIQUE, populated only
--    when something needs to claim about that fixture / venue. Most
--    rows stay NULL.
--
-- 3. source_speakers / source_chapters / source_annotations.
--    Document-level enrichment overlays. Speaker turns and semantic
--    chapters are first-class because they get joined on routinely
--    (claims-by-speaker, claims-by-chapter). source_annotations is the
--    generic long-tail table for sentiment / sub-topic tags / entity
--    mentions and anything that doesn't yet warrant its own table.

-- ─── Part 1: entity_type expansion ────────────────────────────────

-- Migrate any existing matchup rows to 'match' before swapping the constraint.
-- 'match' is the closest semantic equivalent.
UPDATE entities SET entity_type = 'match' WHERE entity_type = 'matchup';

ALTER TABLE entities DROP CONSTRAINT IF EXISTS ck_entity_type;
ALTER TABLE entities ADD CONSTRAINT ck_entity_type CHECK (
    entity_type IN (
        'player',
        'team',
        'advisor',
        'coach',
        'referee',
        'commentator',
        'journalist',
        'match',
        'round',
        'venue'
    )
);

-- ─── Part 2: venue / match entity_id ──────────────────────────────

ALTER TABLE venues
    ADD COLUMN IF NOT EXISTS entity_id UUID UNIQUE REFERENCES entities(entity_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_venues_entity
    ON venues(entity_id) WHERE entity_id IS NOT NULL;

ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS entity_id UUID UNIQUE REFERENCES entities(entity_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_matches_entity
    ON matches(entity_id) WHERE entity_id IS NOT NULL;

COMMENT ON COLUMN venues.entity_id IS
    'Canonical entity for this venue. Populated when the venue is referenced '
    'by claims/predictions/wiki ("Suncorp under lights"). Most rows stay NULL.';

COMMENT ON COLUMN matches.entity_id IS
    'Canonical entity for this match. Replaces the old matchup entity_type so '
    'claims/predictions can target a specific game. Populated when the fixture '
    'is discussed; most rows stay NULL.';

-- ─── Part 3: source_speakers ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS source_speakers (
    segment_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id       UUID NOT NULL REFERENCES source_documents(document_id) ON DELETE CASCADE,
    speaker_entity_id UUID REFERENCES entities(entity_id) ON DELETE SET NULL,
    speaker_label     TEXT,
    start_ts          DOUBLE PRECISION NOT NULL,
    end_ts            DOUBLE PRECISION NOT NULL,
    confidence        DOUBLE PRECISION,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_source_speakers_span CHECK (end_ts >= start_ts)
);

CREATE INDEX IF NOT EXISTS idx_source_speakers_document
    ON source_speakers(document_id);
CREATE INDEX IF NOT EXISTS idx_source_speakers_entity
    ON source_speakers(speaker_entity_id) WHERE speaker_entity_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_source_speakers_doc_start
    ON source_speakers(document_id, start_ts);

COMMENT ON TABLE source_speakers IS
    'Diarised speaker turns over a source document. Coarse-grained span '
    'layer above source_chunks; chunks fall within a turn by timestamp '
    'containment. speaker_entity_id is NULL until the diariser label '
    '(speaker_label) is resolved to a known entity.';

COMMENT ON COLUMN source_speakers.speaker_label IS
    'Raw diariser output ("Speaker 1") used until the label is resolved '
    'to a speaker_entity_id. Persisted so re-resolution is replayable.';

-- ─── Part 4: source_chapters ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS source_chapters (
    chapter_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES source_documents(document_id) ON DELETE CASCADE,
    ordinal     INTEGER NOT NULL,
    title       TEXT NOT NULL,
    summary     TEXT,
    start_ts    DOUBLE PRECISION NOT NULL,
    end_ts      DOUBLE PRECISION NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_source_chapters_span CHECK (end_ts >= start_ts),
    CONSTRAINT uq_source_chapters_doc_ordinal UNIQUE (document_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_source_chapters_document
    ON source_chapters(document_id);
CREATE INDEX IF NOT EXISTS idx_source_chapters_doc_start
    ON source_chapters(document_id, start_ts);

COMMENT ON TABLE source_chapters IS
    'Semantic chapters detected over a source document by the analyse-'
    'transcript pipeline. Used to scope claim extraction (each chapter '
    'gets its own specialist agent) and to attribute claims back to a '
    'chapter for UI navigation.';

-- ─── Part 5: source_annotations ───────────────────────────────────

CREATE TABLE IF NOT EXISTS source_annotations (
    annotation_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id      UUID NOT NULL REFERENCES source_documents(document_id) ON DELETE CASCADE,
    kind             TEXT NOT NULL,
    start_ts         DOUBLE PRECISION,
    end_ts           DOUBLE PRECISION,
    target_entity_id UUID REFERENCES entities(entity_id) ON DELETE SET NULL,
    label            TEXT,
    payload_json     JSONB NOT NULL DEFAULT '{}',
    confidence       DOUBLE PRECISION,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_source_annotations_span CHECK (
        (start_ts IS NULL AND end_ts IS NULL)
        OR (start_ts IS NOT NULL AND end_ts IS NOT NULL AND end_ts >= start_ts)
    )
);

CREATE INDEX IF NOT EXISTS idx_source_annotations_document
    ON source_annotations(document_id);
CREATE INDEX IF NOT EXISTS idx_source_annotations_kind
    ON source_annotations(kind);
CREATE INDEX IF NOT EXISTS idx_source_annotations_doc_kind
    ON source_annotations(document_id, kind);
CREATE INDEX IF NOT EXISTS idx_source_annotations_target
    ON source_annotations(target_entity_id) WHERE target_entity_id IS NOT NULL;

COMMENT ON TABLE source_annotations IS
    'Generic descriptive overlay table for source documents. Use for '
    'sentiment, sub-topic tags, entity mentions, themes — any enrichment '
    'that does not warrant a first-class table. NULL start_ts/end_ts '
    'indicates a document-level annotation.';

COMMENT ON COLUMN source_annotations.kind IS
    'Annotation type — sentiment / subtopic / mention / theme / etc. '
    'Free-form text on purpose so new kinds can be added without schema '
    'changes. Index on (document_id, kind) keeps per-kind queries fast.';
