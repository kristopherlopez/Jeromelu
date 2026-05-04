---
tags: [area/agents, subarea/system, status/live]
---

# Transcription (Analyst's first Transform)

| | |
|---|---|
| **Module** | `services/api/app/analyst/transcribe.py` (orchestrator) + `services/api/app/analyst/diarize.py` (pyannote stage) |
| **Driver** | `python -m app.analyst.transcribe_cli <source_id>` · `make transcribe SOURCE_ID=<uuid>` |
| **Crew counterpart** | [Analyst](../crew/analyst.md) — Analyst's first surface, sitting in front of cleaning / claim extraction. |
| **ETL role** | **Transform.** Reads Scout's audio, produces the structured transcript artefacts every later stage depends on. |
| **Cost** | Deepgram ~$0.30 per 90-min video (nova-3 batch, words only). Pyannote 3.1 runs locally — ~40 min CPU per 45-min audio (~0.9× real-time), single-digit minutes on GPU. |
| **Status** | Phase 2 (Deepgram words + pyannote diarization) live. Single-source CLI shipped. Recurring drain job not yet built. |

> **For audio acquisition** — see [ingestion.md](ingestion.md). That's Scout's job; this module refuses to run if Scout hasn't already populated `audio_s3_key`.

---

## What it does

For one source where `audio_s3_key IS NOT NULL`:

1. **pyannote first** — see [diarize.py](../../../services/api/app/analyst/diarize.py).
   - Download audio from S3, ffmpeg-convert to 16 kHz mono WAV.
   - Run `pyannote/speaker-diarization-3.1` to produce a list of speaker turns.
   - For each turn, compute sliding-window embeddings (2 s window, 0.5 s hop) using `pyannote/wespeaker-voxceleb-resnet34-LM` (256-dim, the embedder bundled with the diarization pipeline). Pick the medoid as the representative.
   - Persist a single JSON to `s3://jeromelu-raw-transcripts/.../{video_id}.pyannote.json` carrying both diarization and per-turn embeddings (medoid + full window list). Idempotent at `JSON_VERSION` — retries skip pyannote unless `make diarize FORCE=1` is run separately.
   - Sub-`MIN_TURN_DURATION` (0.3 s) turns are recorded but get a NULL embedding — the embedder can't produce a stable vector from <300 ms of audio.
2. **Then Deepgram** — for words+timestamps only.
   - Build keyterm vocabulary from the canonical roster (`people` + `teams`). See [extraction-method § keyterm](../../sources/extraction-method.md#keyterm-vocabulary).
   - Presign the audio S3 URL (regional virtual-host endpoint, 15-min validity).
   - POST to Deepgram's prerecorded API with `model=nova-3`, `language=en-AU`, `diarize=false`, `punctuate=true`, `smart_format=true`, `utterances=true`, `paragraphs=true`, `keyterm=<vocabulary>`.
   - Persist Deepgram JSON → `s3://jeromelu-raw-transcripts/.../{video_id}.deepgram.json`. Replayable.
3. **Merge + DB write** (single transaction):
   - `source_documents` — joined utterance text, checksum, language, chunk_count, S3 pointer.
   - `source_speakers` — **one row per pyannote turn**. Each row carries `speaker_label` (`SPEAKER_00`, `SPEAKER_01`, …), `start_ts`, `end_ts`, `embedding` (the medoid 256-dim vector, NULL on too-short turns), and `embedding_model`.
   - `source_chunks` — one row per Deepgram utterance, FK'd to the pyannote turn it overlaps most (max-overlap assignment). `paragraph_break=true` when the within-turn pause to the previous utterance ≥ 1.5 s.
   - `sources.transcription_status='transcribed'`, `extraction_method='deepgram_words+pyannote_v1'`, `diarization_method='pyannote-3.1'`.
4. **Voice identification** — see [identification.md](identification.md). The voiceprint registry is loaded once; for each turn's `embedding_windows`, sliding-window cosine matches vote on a Person. When a Person clears the cosine + agreement thresholds, `source_speakers.speaker_person_id` and `confidence` are populated. With an empty registry every turn stays unidentified — no error.

On failure (Deepgram, network, malformed response, pyannote, ffmpeg, missing HF token): roll back the transcription transaction, mark `sources.transcription_status='failed'` in a separate transaction, raise `TranscriptionError`. Pyannote is run before Deepgram so a pyannote failure costs zero Deepgram dollars. **No fallback chain** — operator inspects, fixes, re-runs with `--force`. Scout's `audio_s3_key` and `ingestion_status='collected'` are not touched, so the audio doesn't get re-downloaded.

`--force` on transcribe replaces the SourceDocument and re-runs Deepgram + DB writes, but **does not** force a pyannote re-run (the pyannote artefact is idempotent at JSON_VERSION). To re-diarize, run `make diarize SOURCE_ID=... FORCE=1` first, then `make transcribe SOURCE_ID=... FORCE=1`.

---

## Hand-off contract

| Table | Fields written | Fields left for later passes |
|---|---|---|
| `source_documents` | `s3_key`, `raw_text`, `transcript_available`, `language`, `checksum`, `chunk_count` | `cleaned_text` (cleaning pass) |
| `source_speakers` | `speaker_label`, `start_ts`, `end_ts`, `embedding`, `embedding_model`, `speaker_person_id`, `confidence` (when a voiceprint match clears thresholds) | The voice/visual fusion provenance columns (Phase 4) |
| `source_chunks` | `raw_text`, `chunk_index`, `start_ts`, `end_ts`, char offsets, `speaker_segment_id`, `paragraph_break` | `clean_text`, `embedding` |
| `sources` | `transcription_status='transcribed'`, `extraction_method='deepgram_words+pyannote_v1'`, `diarization_method='pyannote-3.1'` | — |

This module does **not** write `source_chapters`, `quotes`, `claims`, or `claim_chunks`. Those are subsequent Analyst passes.

---

## Running

```bash
# Prerequisite: Scout has collected the audio
make collect-audio SOURCE_ID=<uuid>

# Then transcribe (pyannote then Deepgram)
make transcribe SOURCE_ID=<uuid>

# Replace any existing SourceDocument (re-runs Deepgram + DB writes; pyannote
# JSON is reused if at current JSON_VERSION).
make transcribe SOURCE_ID=<uuid> FORCE=1

# Force a pyannote re-run (slow on CPU). Then re-transcribe.
make diarize SOURCE_ID=<uuid> FORCE=1
make transcribe SOURCE_ID=<uuid> FORCE=1

# Convenience: do both stages in sequence
make extract-transcript SOURCE_ID=<uuid>
```

Pulls `DEEPGRAM_API_KEY` and `HUGGINGFACE_API_KEY` from project root `.env`. Sets `S3_ENDPOINT=''` so boto3 talks to real AWS.

Expected output:

```
OK
  document_id:        <uuid>
  transcript_s3_key:  youtube/<channel>/<vid>.deepgram.json
  pyannote_s3_key:    youtube/<channel>/<vid>.pyannote.json
  duration_seconds:   2709.6
  speakers_recorded:  4      ← distinct pyannote labels
  turns_recorded:     678    ← SourceSpeaker rows (one per pyannote turn)
  turns_identified:   14     ← turns where a voiceprint match cleared thresholds
  chunks_recorded:    331    ← Deepgram utterances
  chunks_unassigned:  0      ← utterances with no overlapping pyannote turn
  deepgram_model:     nova-3
  pyannote_model:     pyannote/speaker-diarization-3.1
  embedding_model:    pyannote/wespeaker-voxceleb-resnet34-LM
  deepgram_request:   <id>
```

---

## Backlog

- **Phase 4 — visual identification + fusion.** Add face recognition + active-speaker detection from low-res video; fuse with voice match to drive `source_speakers.speaker_person_id`. See [docs/todo/speaker-identification.md](../../todo/speaker-identification.md).
- **Recurring drain job** — APScheduler / cron over `transcription_status IS NULL AND ingestion_status = 'collected'`. Single-source CLI today.
- **Production GPU compute.** Pyannote on Lightsail micro is too slow / memory-tight for prod; Modal / RunPod / dedicated EC2 g4dn worker decision required before this pipeline runs in prod.
- **Cleaning pass** — `source_documents.cleaned_text`, `source_chunks.clean_text`. Today via `/clean-transcript` skill.
- **Embedding pass** — `source_chunks.embedding` (text embedding, separate from the voice embedding on `source_speakers`). Not yet built.
- **Player alias backfill** — `people.aliases` is empty; populating it improves keyterm coverage for nicknames (the biggest single keyterm-pool win).
- **Topic-targeted keyterms** — derive per-source from video title + description + channel focus, replacing the global roster pool. See [extraction-method § keyterm](../../sources/extraction-method.md#keyterm-vocabulary) discussion.
- **`agent_runs` rows** — deterministic transcription currently has no canonical run log. Standardising would unify cost / latency dashboards with Scout's agentic discovery surface.

---

## Related

- [Analyst (crew)](../crew/analyst.md)
- [Audio ingestion (Scout)](ingestion.md) — predecessor stage
- [Sources § extraction method](../../sources/extraction-method.md) — full pipeline cost model, keyterm strategy, error handling
- [Voice Identification (Phase 3)](identification.md) — successor surface that populates `speaker_person_id` from the embeddings this pipeline produces
- [Speaker Identification plan](../../todo/speaker-identification.md) — Phase 1 ✅, Phase 2 ✅, Phase 3 ✅, Phase 4 (visual + fusion) next
- [Migration 044](../../../packages/db/migrations/044_audio_first_extract.sql) (chunks rebuilt with speaker FK), [Migration 045](../../../packages/db/migrations/045_split_ingestion_transcription.sql) (status fields split), [Migration 046](../../../packages/db/migrations/046_chunk_paragraph_break.sql) (paragraph_break), [Migration 047](../../../packages/db/migrations/047_pyannote_diarization.sql) (voice embeddings on source_speakers), [Migration 048](../../../packages/db/migrations/048_person_voiceprints.sql) (voiceprint registry)
