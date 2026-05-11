-- 053: source_face_detections — every face detected during visual ID,
-- with its embedding kept (instead of dropped into the face-track JSON
-- and forgotten). The face-track JSON is still the per-frame overlay
-- cache; this table is the canonical embedding store and the basis for
-- intra-source face clustering (Slice B).
--
-- Why a separate table from person_face_embeddings: that table is the
-- *registry* (one row per enrolled exemplar; small, queried at match
-- time). This is the *raw observation log* (one row per detection ≈
-- thousands per source; queried at review time for clustering and at
-- ETL time for matching). Different access patterns, different growth
-- rates, different lifecycles — registry persists, observations can
-- be re-derived from the audio + video.
--
-- HNSW index for cosine k-NN — used both for intra-source clustering
-- (find detections similar to a sampled point) and cross-source label
-- propagation (find detections across other sources similar to a
-- confirmed cluster centroid).
--
-- cluster_id is INT NULL. Populated by a per-source clustering pass
-- (Slice B PR 2) after detections land. NULL means "not yet clustered"
-- and is the expected initial state for every row.

BEGIN;

CREATE TABLE source_face_detections (
    detection_id      UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id         UUID         NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    frame_ts          REAL         NOT NULL,
    -- bbox in source-frame pixel coordinates: [x1, y1, x2, y2].
    -- Stored as four columns so they're queryable; bbox_x1 < bbox_x2
    -- and bbox_y1 < bbox_y2 enforced below.
    bbox_x1           REAL         NOT NULL,
    bbox_y1           REAL         NOT NULL,
    bbox_x2           REAL         NOT NULL,
    bbox_y2           REAL         NOT NULL,
    det_score         REAL         NOT NULL,
    -- 512-dim InsightFace `buffalo_l` ArcFace, same model as
    -- person_face_embeddings so cross-table cosine similarity is
    -- directly comparable.
    embedding         vector(512)  NOT NULL,
    embedding_model   TEXT         NOT NULL,
    -- Inner-lip openness, kept here for downstream ASD / heuristics.
    mouth_opening     REAL,
    -- The match result from this detection's visual ID pass, if any.
    -- Mirrors the face-track JSON's per-face person_id/similarity but
    -- now alongside the embedding that produced the match.
    matched_person_id UUID         REFERENCES people(person_id) ON DELETE SET NULL,
    match_score       REAL,
    -- Populated by the clustering pass (Slice B PR 2). NULL = not yet
    -- clustered. Per-source identifier — clusters are local to a
    -- source; cross-source linking is via embedding similarity, not
    -- shared IDs.
    cluster_id        INTEGER,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT ck_source_face_detections_bbox_x CHECK (bbox_x2 > bbox_x1),
    CONSTRAINT ck_source_face_detections_bbox_y CHECK (bbox_y2 > bbox_y1)
);

-- Source-scoped listing is the dominant query: "all detections for
-- this source ordered by ts". (source_id, frame_ts) supports both
-- predicate and sort from the index.
CREATE INDEX idx_source_face_detections_source_ts
    ON source_face_detections(source_id, frame_ts);

-- Per-source-per-cluster lookup for the runs view ("all detections in
-- cluster N of source S"). Partial — clusters are only populated
-- after the clustering pass runs.
CREATE INDEX idx_source_face_detections_source_cluster
    ON source_face_detections(source_id, cluster_id)
    WHERE cluster_id IS NOT NULL;

-- HNSW on embedding for cosine k-NN. Backs both intra-source clustering
-- (kNN per sample) and cross-source propagation queries ("find all
-- detections across all sources within cosine X of this centroid").
CREATE INDEX idx_source_face_detections_hnsw
    ON source_face_detections
    USING hnsw (embedding vector_cosine_ops);

COMMIT;
