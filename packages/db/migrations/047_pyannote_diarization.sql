-- 047: pyannote diarization + per-turn voice embeddings.
--
-- Phase 2 of speaker-identification. Replaces Deepgram's diarizer with
-- pyannote.audio while keeping Deepgram for words + timestamps. Each
-- source_speakers turn now carries a representative voice embedding
-- (medoid of sliding-window 2s/0.5s-hop embeddings from the audio span).
-- These embeddings are the substrate for Phase 3 voice enrollment +
-- identification.
--
-- Embedding model: pyannote/wespeaker-voxceleb-resnet34-LM, the embedder
-- bundled with the speaker-diarization-3.1 pipeline (256-dim). Stored as
-- pgvector for HNSW k-NN matching against `person_voiceprints` in Phase 3.
--
-- New `extraction_method` value: 'deepgram_words+pyannote_v1'. Old
-- 'deepgram_v1' rows are not touched — re-running with --force will
-- migrate them on demand.
--
-- New `diarization_method` column on `sources` records which diarizer
-- produced the source_speakers rows for this source. NULL on legacy
-- rows; 'pyannote-3.1' on new rows.

BEGIN;

ALTER TABLE source_speakers
    ADD COLUMN embedding vector(256),
    ADD COLUMN embedding_model TEXT;

ALTER TABLE sources
    ADD COLUMN diarization_method TEXT;

-- Extend the existing extraction_method check to allow the new pipeline.
ALTER TABLE sources DROP CONSTRAINT IF EXISTS ck_sources_extraction_method;
ALTER TABLE sources
    ADD CONSTRAINT ck_sources_extraction_method
    CHECK (extraction_method IS NULL
           OR extraction_method IN (
               'deepgram_v1',
               'deepgram_words+pyannote_v1',
               'youtube_captions'
           ));

COMMIT;
