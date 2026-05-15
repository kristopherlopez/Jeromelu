---
tags: [area/operations, data-lineage]
---

# Lineage: person_voiceprints

[Schema: data-catalogue/person_voiceprints.md](../data-catalogue/person_voiceprints.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Operator enrollment (manual) | — | **Primary** today — operator selects a span of audio explicitly attributed to a Person |
| Phase 5 cross-modal compounding (planned) | — | Auto-confirmation when face+voice agree above threshold |

## Writers

- `services/api/app/routers/sources.py` — admin enrollment endpoints (operator selects span → embed → INSERT)
- `services/api/app/analyst/identify_voice.py` — voice fingerprint matcher; reads existing voiceprints to attribute new turns. Phase 5 cross-modal will write back as `created_by='auto-confirmed'`

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `voiceprint_id` | derived | UUID, DB-side default |
| `person_id` | enrollment | FK → people; the human this voiceprint represents |
| `source_id` | enrollment | FK → sources; the source the audio came from (NULL for synthetic enrollment) |
| `start_ts`, `end_ts` | enrollment | Audio span |
| `embedding` | embedder | 256-dim wespeaker / community-1 / pyannote model output |
| `embedding_model` | embedder | Denormalised so model swap doesn't need a migration |
| `created_by` | writer | `manual` (operator) or `auto-confirmed` (cross-modal Phase 5) |
| `created_at` | derived | DB default `now()` |

## Notes

- Per [[feedback_pyannote_full_wav_for_bulk]]: bulk enrollment pre-converts m4a→WAV once and slices in-memory rather than ffmpeg-cropping per span.
- Per [[feedback_transcribe_isolation]]: voice embedding inference lives in `services/gpu` or a worker, not the API container.
- The HNSW index supports cosine k-NN at match time. Registry is small today (single-digit hosts × ~60 voiceprints each).
