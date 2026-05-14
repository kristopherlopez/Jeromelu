---
tags: [area/operations, data-lineage]
---

# Lineage: source_speakers

[Schema: data-catalogue/source_speakers.md](../data-catalogue/source_speakers.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Diarisation (Pyannote 4 / Deepgram) | — (raw audio in `s3://jeromelu-raw-audio`) | **Primary** — speaker turn boundaries |
| Voice fingerprint matching (Pyannote enrollment) | — | Sets `speaker_person_id` after diariser labels are resolved to known voices |
| Visual face matching | — | Future cross-modal compounding (per `docs/todo/speaker-identification-plan.md`) |

## Writers

- `services/api/app/analyst/transcribe.py` — runs diarisation against the source audio (per [[feedback_transcribe_isolation]] this lives in services/gpu or workers, not the API container); INSERTs one row per detected speaker turn
- `services/api/app/analyst/identify_voice.py` — voice-fingerprint matcher; UPDATEs `speaker_person_id` when a diariser-labelled turn matches a known [people](people.md) voiceprint
- Voice cluster labeller (mig 069 — per [[project_voice_cluster_label_layer]]) — HDBSCAN/manual/face-driven labels live in `source_speakers.cluster_label`; reads use `coalesce(cluster_label, speaker_label)`

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `segment_id` | derived | UUID, DB-side default |
| `document_id` | scope | FK → source_documents (CASCADE) |
| `speaker_person_id` | voice/face matcher | FK → people (SET NULL); NULL for unattributed turns |
| `speaker_label` | diariser | Raw label (`Speaker 1`, `Speaker 2`) when person not yet resolved |
| `cluster_label` | cluster labeller (mig 069) | HDBSCAN cluster id / manual label / face-driven label |
| `start_ts`, `end_ts` | diariser | Seconds |
| `confidence` | diariser | 0-1 |
| `created_at` | derived | DB default `now()` |

## Notes

- Coarse-grained span layer above [source_chunks](source_chunks.md). Chunks fall within a speaker turn by timestamp containment.
- Pyannote 4 + community-1 model on SageMaker g5 per recent commits.
- Bulk enrollment uses the full WAV (not per-span ffmpeg crops) per [[feedback_pyannote_full_wav_for_bulk]].
