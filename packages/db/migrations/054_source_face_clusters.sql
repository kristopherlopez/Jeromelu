-- 054: source_face_clusters — per-cluster metadata layer on top of the
-- detection table (mig 053). Each row is one face cluster within one
-- source, identified by (source_id, cluster_id) where cluster_id
-- matches the integer assigned by the HDBSCAN pass in face_clusters.py.
--
-- Why this exists: source_face_detections.cluster_id groups the
-- detections, but the cluster itself has no first-class home for the
-- decisions an operator makes about it — "this is a portrait on the
-- wall, ignore", "this is the regular co-host, attribute to Person X",
-- or just a friendly label. This table captures all of that plus the
-- diagnostic stats that informed the auto-tag heuristic so future
-- re-runs are explainable.
--
-- The (source_id, cluster_id) compound key is intentional: cluster IDs
-- are local to a source (HDBSCAN doesn't link across sources), so
-- there's no global Cluster entity. Cross-source linking lives in the
-- embeddings table (mig 053 + HNSW).
--
-- The kind enum is operator-facing:
--   'person'   — represents a real on-screen speaker; default-included
--   'portrait' — a static face (wall art, framed photo, poster);
--                default-excluded from the runs view so the operator
--                isn't scrolling through every-frame appearances of
--                wall decor.
--   'noise'    — small cluster that's mostly partial faces / detector
--                jitter; default-excluded.
--   NULL       — unreviewed, default-included so it surfaces for triage.

BEGIN;

CREATE TABLE source_face_clusters (
    source_id           UUID         NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    cluster_id          INTEGER      NOT NULL,
    -- Operator override or auto-tag (whichever was most recent). NULL
    -- means "not yet reviewed or auto-classified".
    kind                TEXT,
    -- Operator override label — "Denan Kemp", "Wall portrait — Brad
    -- Fittler", etc. When NULL, the UI falls back to "Cluster A"-style
    -- generated labels.
    label               TEXT,
    -- True = hide from default runs view. The auto-tagger sets this
    -- when kind in ('portrait', 'noise'); operator can flip.
    excluded            BOOLEAN      NOT NULL DEFAULT false,
    notes               TEXT,
    -- Cluster size at last analysis pass. Re-derivable from detections
    -- but useful for "show cluster A (1,739 detections)" in the UI
    -- without a JOIN.
    detection_count     INTEGER      NOT NULL DEFAULT 0,
    -- Diagnostic stats from the heuristic pass — kept so re-running the
    -- analyser is observably idempotent and operators can see WHY a
    -- cluster was auto-tagged. All in source-frame pixel / score units.
    mouth_open_std      REAL,
    centroid_std        REAL,
    temporal_density    REAL,
    -- Separate column from `kind` so we can distinguish "operator
    -- overrode the auto-tag" from "auto-tag landed and operator
    -- accepted it implicitly". Empty string never; NULL = not run yet.
    detected_kind       TEXT,
    -- The Person this cluster has been bulk-assigned to, if any.
    -- Mirrors source_face_detections.matched_person_id at the cluster
    -- granularity so the runs view doesn't need to aggregate per
    -- detection on every render. Updated by the bulk-assign endpoint.
    attributed_person_id UUID        REFERENCES people(person_id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    PRIMARY KEY (source_id, cluster_id),

    CONSTRAINT ck_source_face_clusters_kind
        CHECK (kind IS NULL OR kind IN ('person', 'portrait', 'noise')),
    CONSTRAINT ck_source_face_clusters_detected_kind
        CHECK (detected_kind IS NULL OR detected_kind IN ('person', 'portrait', 'noise'))
);

-- Per-source listing — every read for /face-runs filters by source_id.
CREATE INDEX idx_source_face_clusters_source ON source_face_clusters(source_id);

-- Cross-source rollups ("how many portrait clusters does the library
-- have?") and the future propagation preview query.
CREATE INDEX idx_source_face_clusters_kind
    ON source_face_clusters(kind)
    WHERE kind IS NOT NULL;

COMMIT;
