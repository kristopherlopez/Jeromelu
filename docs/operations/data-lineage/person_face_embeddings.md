---
tags: [area/operations, data-lineage]
---

# Lineage: person_face_embeddings

[Schema: data-catalogue/person_face_embeddings.md](../data-catalogue/person_face_embeddings.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Operator enrollment (manual) | — | Operator picks a face from a frame and attributes to a Person |
| Headshot bulk enrollment | — | `created_by='headshot'` for static headshot ingestion |
| Phase 5 cross-modal auto-confirmation | — | Planned — face+voice agreement above threshold writes back |

## Writers

- `services/api/app/routers/sources.py` — admin enrollment endpoints
- `services/api/app/analyst/visual_id.py` — visual-ID pipeline; matches against this registry
- `services/api/app/analyst/face_clusters.py` — face clustering; can be a source of bulk-attribution events that feed back here

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `face_embedding_id` | derived | UUID, DB-side default |
| `person_id` | enrollment | FK → people |
| `source_id` | enrollment | FK → sources; the source the frame came from (NULL for static headshots) |
| `frame_ts` | enrollment | Where in the source the face was captured (NULL for headshots) |
| `embedding` | embedder | 512-dim InsightFace `buffalo_l` ArcFace |
| `embedding_model` | embedder | Denormalised |
| `created_by` | writer | `manual`, `headshot`, or `auto-confirmed` |
| `created_at` | derived | DB default `now()` |

## Notes

- Embedding dimension matches [source_face_detections](source_face_detections.md) — same buffalo_l model, so cross-table cosine similarity is directly comparable.
- HNSW index for cosine k-NN at match time.
