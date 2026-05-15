---
tags: [area/operations, data-catalogue]
---

# source_face_detections

[← Data Catalogue](README.md) · [Lineage](../data-lineage/source_face_detections.md) · Layer 3 — Content & claims

Raw face-detection observation log — one row per detected face per frame during visual ID. The face-track JSON overlay cache stays as the per-frame bundle; this table is the canonical embedding store and the basis for intra-source face clustering. Different access pattern from [person_face_embeddings](person_face_embeddings.md) (the *registry*; small, queried at match time) — this is the *observation log* (thousands per source; queried at review and ETL time). Added in mig 053.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| detection_id | UUID | PK | uuid4 | |
| source_id | UUID | no | | FK → sources (CASCADE) |
| frame_ts | float | no | | When in the source this frame was sampled (seconds) |
| bbox_x1 | float | no | | Source-frame pixel coordinates: top-left x |
| bbox_y1 | float | no | | top-left y |
| bbox_x2 | float | no | | bottom-right x |
| bbox_y2 | float | no | | bottom-right y |
| det_score | float | no | | Detector confidence |
| embedding | vector(512) | no | | InsightFace buffalo_l ArcFace; same model as person_face_embeddings |
| embedding_model | text | no | | Denormalised |
| mouth_opening | float | yes | | Inner-lip openness, kept for downstream Active Speaker Detection / heuristics |
| matched_person_id | UUID | yes | | FK → people (SET NULL). The match result from this detection's visual-ID pass |
| match_score | float | yes | | Similarity score for the match |
| cluster_id | int | yes | | Set by intra-source clustering pass (HDBSCAN). Per-source — clusters are local to a source. NULL = not yet clustered |
| created_at | timestamptz | no | now() | |

**Indexes:** (source_id, frame_ts) for source-scoped listing; (source_id, cluster_id) partial WHERE NOT NULL; embedding HNSW (vector_cosine_ops)
**Check:** `bbox_x2 > bbox_x1`; `bbox_y2 > bbox_y1`
**FK:** source_id → sources (CASCADE); matched_person_id → people (SET NULL)

The HNSW index supports both intra-source clustering (kNN per sample) and cross-source label propagation ("find detections across other sources within cosine X of this confirmed cluster centroid").
