---
tags: [area/operations, data-catalogue]
---

# person_voiceprints

[← Data Catalogue](README.md) · [Lineage](../data-lineage/person_voiceprints.md) · Layer 3 — Content & claims

Voice fingerprint registry for speaker identification. Each row is one sliding-window embedding (2s window, 0.5s hop) from a span of audio explicitly attributed to a [people](people.md) row. Multiple rows per enrollment session capture acoustic variation; multiple enrollment sessions per Person compound the registry over time. Added in mig 048.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| voiceprint_id | UUID | PK | uuid4 | |
| person_id | UUID | no | | FK → people (CASCADE) |
| source_id | UUID | yes | | FK → sources (SET NULL); the source the audio came from |
| start_ts | float | no | | Seconds |
| end_ts | float | no | | Seconds |
| embedding | vector(256) | no | | Voice embedding (model varies — e.g. wespeaker, community-1) |
| embedding_model | text | no | | Denormalised on row so model swap doesn't need a migration |
| created_by | text | no | `manual` | `manual` (operator enrollment) or `auto-confirmed` (Phase 5 cross-modal compounding) |
| created_at | timestamptz | no | now() | |

**Indexes:** person_id; source_id (partial: WHERE NOT NULL); embedding HNSW (vector_cosine_ops)
**Check:** `end_ts >= start_ts`; `created_by IN ('manual', 'auto-confirmed')`
**FK:** person_id → people (CASCADE); source_id → sources (SET NULL)

The HNSW index on embedding backs fast cosine-similarity k-NN at match time. Registry growth is modest (single-digit hosts × ~60 voiceprints per host); index choice is low-stakes today. See [[feedback_pyannote_full_wav_for_bulk]] for enrollment perf notes.
