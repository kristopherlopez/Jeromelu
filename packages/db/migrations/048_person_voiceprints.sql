-- 048: person_voiceprints — voice fingerprint registry for Phase 3 ID.
--
-- Each voiceprint row is one sliding-window embedding (2 s window,
-- 0.5 s hop) from a span of audio explicitly attributed to a Person.
-- Multiple rows per enrollment session — capturing acoustic variation
-- within the span — and multiple enrollment sessions per Person over
-- time, so the registry compounds (Phase 5).
--
-- Embedding model is denormalised on the row so a future model swap
-- (community-1, WavLM, etc.) doesn't require a migration; we simply
-- start writing rows under a different `embedding_model` and matching
-- can scope by model name as needed.
--
-- HNSW index on embedding for fast cosine-similarity k-NN. The expected
-- registry size (single-digit hosts × ~60 voiceprints per host) makes
-- index choice low-stakes today, but we'll grow into it as Phase 5
-- auto-confirmations stack up.
--
-- created_by tracks provenance: 'manual' from operator enrollment,
-- 'auto-confirmed' from Phase 5 cross-modal compounding (face+voice
-- agreement above threshold).

BEGIN;

CREATE TABLE person_voiceprints (
    voiceprint_id   UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id       UUID         NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
    source_id       UUID         REFERENCES sources(source_id) ON DELETE SET NULL,
    start_ts        REAL         NOT NULL,
    end_ts          REAL         NOT NULL,
    embedding       vector(256)  NOT NULL,
    embedding_model TEXT         NOT NULL,
    created_by      TEXT         NOT NULL DEFAULT 'manual',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ck_person_voiceprints_span
        CHECK (end_ts >= start_ts),
    CONSTRAINT ck_person_voiceprints_created_by
        CHECK (created_by IN ('manual', 'auto-confirmed'))
);

CREATE INDEX idx_person_voiceprints_person
    ON person_voiceprints(person_id);

CREATE INDEX idx_person_voiceprints_source
    ON person_voiceprints(source_id)
    WHERE source_id IS NOT NULL;

CREATE INDEX idx_person_voiceprints_embedding_hnsw
    ON person_voiceprints
    USING hnsw (embedding vector_cosine_ops);

COMMIT;
