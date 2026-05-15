---
tags: [area/operations, data-catalogue]
---

# person_face_embeddings

[← Data Catalogue](README.md) · [Lineage](../data-lineage/person_face_embeddings.md) · Layer 3 — Content & claims

Face fingerprint registry — visual-ID counterpart to [person_voiceprints](person_voiceprints.md). One row per enrolled face exemplar attributed to a [people](people.md) row, captured from headshot images or in-source frames. Multiple rows per Person let the registry capture variation (angle, lighting, hair, age) and compound via Phase 5 cross-modal auto-confirmation. Added in mig 049.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| face_embedding_id | UUID | PK | uuid4 | |
| person_id | UUID | no | | FK → people (CASCADE) |
| source_id | UUID | yes | | FK → sources (SET NULL); the source the frame came from (NULL for headshots) |
| frame_ts | float | yes | | Where in the source the face was captured (NULL for static headshots) |
| embedding | vector(512) | no | | InsightFace `buffalo_l` ArcFace output |
| embedding_model | text | no | | Denormalised on row so model swap (ArcFace → AdaFace, etc.) doesn't need a migration |
| created_by | text | no | `manual` | `manual` (operator enrollment), `headshot` (bulk headshot enrollment), `auto-confirmed` (Phase 5 cross-modal compounding) |
| created_at | timestamptz | no | now() | |

**Indexes:** person_id; source_id (partial: WHERE NOT NULL); embedding HNSW (vector_cosine_ops)
**Check:** `created_by IN ('manual', 'headshot', 'auto-confirmed')`
**FK:** person_id → people (CASCADE); source_id → sources (SET NULL)

The HNSW index on embedding backs cosine k-NN at visual-ID match time. Embedding dimension matches [source_face_detections](source_face_detections.md) (both 512-dim from the same buffalo_l model) so cross-table cosine similarity is directly comparable.
