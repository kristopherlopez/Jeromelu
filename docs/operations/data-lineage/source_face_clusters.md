---
tags: [area/operations, data-lineage]
---

# Lineage: source_face_clusters

[Schema: data-catalogue/source_face_clusters.md](../data-catalogue/source_face_clusters.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Per-source HDBSCAN clustering pass | — (over [source_face_detections](source_face_detections.md) embeddings) | **Primary** — one row per cluster per source |
| Operator review | — | Sets `kind`, `label`, `excluded`, `notes` |
| Bulk-assign endpoint | — | Sets `attributed_person_id` for cluster-granularity Person linking |

## Writers

- `services/api/app/analyst/face_clusters.py` — clustering + auto-tagging pass; INSERTs cluster rows with diagnostic stats (`mouth_open_std`, `centroid_std`, `temporal_density`) and computed `detected_kind`
- `services/api/app/routers/sources.py` — review endpoints; UPDATEs `kind`, `label`, `excluded`, `notes` based on operator input
- Bulk-assign endpoint — UPDATEs `attributed_person_id` plus the matching `source_face_detections.matched_person_id`

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `source_id`, `cluster_id` | clusterer | Compound PK; cluster_id matches `source_face_detections.cluster_id` |
| `kind` | operator override / auto-tag | `person`, `portrait`, `noise`, NULL |
| `label` | operator | Override label; UI falls back to "Cluster A"-style when NULL |
| `excluded` | auto-tag / operator | Defaults false; auto-tagger sets true for `kind IN ('portrait', 'noise')`; operator can flip |
| `notes` | operator | |
| `detection_count` | clusterer | Cluster size at last analysis pass |
| `mouth_open_std`, `centroid_std`, `temporal_density` | clusterer | Diagnostic stats (auto-tag explainability) |
| `detected_kind` | auto-tagger | Separate from `kind` so we distinguish operator-override vs auto-accepted |
| `attributed_person_id` | bulk-assign | FK → people (SET NULL); cluster-granularity Person attribution |
| `created_at`, `updated_at` | derived | DB defaults |

## Notes

- `cluster_id` is local to a source (HDBSCAN doesn't link across sources). No global Cluster entity.
- Cross-source linking happens in [source_face_detections](source_face_detections.md) via embedding similarity (HNSW).
