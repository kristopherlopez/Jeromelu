-- 044: Audio-first transcript extraction.
--
-- Switches Scout's transcript-pull surface from YouTube auto-captions to
-- yt-dlp + Deepgram (diarisation + keyterm boosting). Two structural
-- changes follow:
--
--   1. `sources` carries new provenance fields:
--        - audio_s3_key      pointer to the raw audio (m4a) in
--                            s3://jeromelu-raw-audio. Kept long-term for
--                            re-transcription and voice fine-tuning.
--        - extraction_method 'deepgram_v1' for new pipeline,
--                            'youtube_captions' for legacy backfills,
--                            NULL for sources discovered but not yet ingested.
--
--   2. `source_chunks` is rebuilt with:
--        - speaker_segment_id FK to source_speakers (now Scout-owned, not
--          a downstream Transform table).
--        - tighter column order (identifiers → time → space → text → semantic).
--        - UNIQUE (document_id, chunk_index) to catch double-writes.
--
-- The legacy 221k auto-caption-era chunks are preserved in
-- `source_chunks_v1` for inspection. Quotes / claim_chunks / claims are
-- empty in dev right now (no Analyst output yet) so we re-point their
-- FKs at the new table without touching data.
--
-- After this migration, all 2k+ existing `sources` rows have
-- `extraction_method=NULL` (their chunks live in source_chunks_v1, not
-- the canonical table). They are not re-flipped to `pending` — re-extract
-- them via a separate backfill script when ready.

BEGIN;

-- 1. Sources: provenance fields ----------------------------------------------

ALTER TABLE sources
    ADD COLUMN audio_s3_key      TEXT,
    ADD COLUMN extraction_method TEXT;

ALTER TABLE sources
    ADD CONSTRAINT ck_sources_extraction_method
    CHECK (extraction_method IS NULL
           OR extraction_method IN ('deepgram_v1', 'youtube_captions'));

-- 2. Drop FKs targeting source_chunks before renaming ------------------------
-- Renaming the table would silently re-target these FKs at source_chunks_v1.
-- Drop them now so we can re-add them against the new canonical table.

ALTER TABLE quotes        DROP CONSTRAINT IF EXISTS quotes_chunk_id_fkey;
ALTER TABLE claim_chunks  DROP CONSTRAINT IF EXISTS claim_chunks_chunk_id_fkey;

-- 3. Archive existing chunks --------------------------------------------------

ALTER TABLE source_chunks RENAME TO source_chunks_v1;
ALTER INDEX idx_source_chunks_document RENAME TO idx_source_chunks_v1_document;

-- 4. Rebuild source_chunks ----------------------------------------------------

CREATE TABLE source_chunks (
    chunk_id            UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id         UUID        NOT NULL REFERENCES source_documents(document_id) ON DELETE CASCADE,
    speaker_segment_id  UUID        REFERENCES source_speakers(segment_id) ON DELETE SET NULL,
    chunk_index         INTEGER     NOT NULL,
    start_ts            REAL,
    end_ts              REAL,
    start_offset        INTEGER,
    end_offset          INTEGER,
    raw_text            TEXT        NOT NULL,
    clean_text          TEXT,
    embedding           vector(1536),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_source_chunks_ts_span
        CHECK (start_ts IS NULL OR end_ts IS NULL OR end_ts >= start_ts),
    CONSTRAINT uq_source_chunks_doc_index
        UNIQUE (document_id, chunk_index)
);

CREATE INDEX idx_source_chunks_document
    ON source_chunks(document_id);

CREATE INDEX idx_source_chunks_speaker
    ON source_chunks(speaker_segment_id)
    WHERE speaker_segment_id IS NOT NULL;

-- 5. Re-establish downstream FKs pointing at the new table -------------------

ALTER TABLE quotes
    ADD CONSTRAINT quotes_chunk_id_fkey
    FOREIGN KEY (chunk_id) REFERENCES source_chunks(chunk_id);

ALTER TABLE claim_chunks
    ADD CONSTRAINT claim_chunks_chunk_id_fkey
    FOREIGN KEY (chunk_id) REFERENCES source_chunks(chunk_id) ON DELETE CASCADE;

COMMIT;
