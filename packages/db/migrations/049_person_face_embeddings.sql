-- 049: person_face_embeddings — face-fingerprint registry for Phase 4 visual ID.
--
-- Mirrors person_voiceprints (mig 048) — same enrollment / matching shape,
-- different modality. Each row is one face embedding from a frame
-- explicitly attributed to a Person. Multiple rows per Person let the
-- registry capture acoustic^Wvisual variation (different angles,
-- lighting, hair, age) and compound over time via Phase 5 cross-modal
-- auto-confirmations.
--
-- Embedding model is denormalised on the row so a future model swap
-- (e.g. ArcFace -> AdaFace) doesn't require a migration.
--
-- HNSW index on embedding for cosine k-NN at match time. Embedding
-- dimension is 512 (InsightFace `buffalo_l` ArcFace output).

BEGIN;

CREATE TABLE person_face_embeddings (
    face_embedding_id UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id         UUID         NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
    source_id         UUID         REFERENCES sources(source_id) ON DELETE SET NULL,
    frame_ts          REAL,        -- where in the source the face was captured
    embedding         vector(512)  NOT NULL,
    embedding_model   TEXT         NOT NULL,
    created_by        TEXT         NOT NULL DEFAULT 'manual',
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ck_person_face_embeddings_created_by
        CHECK (created_by IN ('manual', 'headshot', 'auto-confirmed'))
);

CREATE INDEX idx_person_face_embeddings_person
    ON person_face_embeddings(person_id);

CREATE INDEX idx_person_face_embeddings_source
    ON person_face_embeddings(source_id)
    WHERE source_id IS NOT NULL;

CREATE INDEX idx_person_face_embeddings_hnsw
    ON person_face_embeddings
    USING hnsw (embedding vector_cosine_ops);

COMMIT;
