---
tags: [area/operations, data-catalogue]
---

# source_face_clusters

[← Data Catalogue](README.md) · [Lineage](../data-lineage/source_face_clusters.md) · Layer 3 — Content & claims

Per-cluster metadata layer above [source_face_detections](source_face_detections.md). Each row is one face cluster within one source, identified by `(source_id, cluster_id)` matching the integer assigned by HDBSCAN. Captures operator decisions ("this is wall art, ignore", "this is the regular co-host") plus the diagnostic stats that informed the auto-tag heuristic so future re-runs are explainable. Added in mig 054.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| source_id | UUID | PK part | | FK → sources (CASCADE) |
| cluster_id | int | PK part | | Local to the source (HDBSCAN doesn't link across sources) |
| kind | text | yes | | Operator override / auto-tag: `person` (default-included), `portrait` (default-excluded — wall art / posters), `noise` (default-excluded — partial faces / detector jitter), NULL (unreviewed; default-included for triage) |
| label | text | yes | | Operator override label ("Denan Kemp", "Wall portrait — Brad Fittler"). Falls back to "Cluster A"-style when NULL |
| excluded | bool | no | false | True = hide from default runs view. Auto-tagger sets when `kind IN ('portrait', 'noise')`; operator can flip |
| notes | text | yes | | |
| detection_count | int | no | 0 | Cluster size at last analysis pass; re-derivable from detections but useful for "cluster A (1,739 detections)" UI without a JOIN |
| mouth_open_std | float | yes | | Diagnostic stat from heuristic pass (auto-tag explainability) |
| centroid_std | float | yes | | Same |
| temporal_density | float | yes | | Same |
| detected_kind | text | yes | | Separate from `kind` so we distinguish operator-override from auto-tag-accepted-implicitly |
| attributed_person_id | UUID | yes | | FK → people (SET NULL). Bulk-assigned Person at cluster granularity (mirrors `source_face_detections.matched_person_id` for runs view perf) |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | |

**PK:** (source_id, cluster_id) compound — cluster IDs are local to a source
**Indexes:** source_id; kind (partial: WHERE NOT NULL)
**Check:** `kind IN (NULL, 'person', 'portrait', 'noise')`; `detected_kind IN (NULL, 'person', 'portrait', 'noise')`
**FK:** source_id → sources (CASCADE); attributed_person_id → people (SET NULL)

Cross-source linking is via embedding similarity in `source_face_detections` (HNSW), not via shared cluster_id.
