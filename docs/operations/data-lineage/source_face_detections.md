---
tags: [area/operations, data-lineage]
---

# Lineage: source_face_detections

[Schema: data-catalogue/source_face_detections.md](../data-catalogue/source_face_detections.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Visual ID detection pass (per-source) | — (raw frames in `s3://jeromelu-raw-audio` / video archives) | **Primary** — every detected face per frame |

## Writers

- `services/api/app/analyst/visual_id.py` — runs face detection on source frames, embeds with InsightFace `buffalo_l` ArcFace, INSERTs one row per detected face
- `services/api/app/analyst/remote.py` — remote SageMaker invocation wrapper (per [[feedback_transcribe_isolation]] heavy ML stays out of the API container)
- `services/api/app/analyst/face_clusters.py` — clustering pass that UPDATEs `cluster_id` after detections land

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `detection_id` | derived | UUID, DB-side default |
| `source_id` | scope | FK → sources (CASCADE) |
| `frame_ts` | detector | Sampling timestamp |
| `bbox_x1`, `bbox_y1`, `bbox_x2`, `bbox_y2` | detector | Pixel coords |
| `det_score` | detector | Confidence |
| `embedding` | embedder | 512-dim ArcFace |
| `embedding_model` | embedder | Denormalised |
| `mouth_opening` | detector | Inner-lip openness; downstream Active Speaker Detection / heuristics |
| `matched_person_id` | matcher | FK → people (SET NULL); the Person matched at visual-ID time |
| `match_score` | matcher | Cosine similarity to the matched Person's [person_face_embeddings](person_face_embeddings.md) |
| `cluster_id` | clusterer | INTEGER; assigned by intra-source HDBSCAN pass. NULL = not yet clustered. Per-source — clusters local to a source |
| `created_at` | derived | DB default `now()` |

## Notes

- Different access pattern from [person_face_embeddings](person_face_embeddings.md): this is the *raw observation log* (thousands per source), that one is the *registry* (small, queried at match time).
- Cross-source linking is via embedding similarity (HNSW), not shared cluster IDs.
- The cluster metadata layer lives in [source_face_clusters](source_face_clusters.md).
