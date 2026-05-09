---
tags: [area/agents, subarea/system, status/live]
---

# Transcription Pipeline

The orchestration surface for the audio → identified-transcript flow. Takes an audio (and optionally video) source from Scout and walks it through diarization, ASR, merge, and speaker identification — producing the structured transcript every downstream pass (cleaning, claim extraction, the wiki, the ledger) reads from.

This doc is the **end-to-end view**. For matching algorithm detail (voice + face + fusion), see [speaker-identification.md](speaker-identification.md). For audio acquisition, see [ingestion.md](ingestion.md). The rest of this doc owns the pyannote / Deepgram / merge stages and the orchestration that ties everything together.

## Pipeline overview

```
audio (Scout)  ─┬─> pyannote ───────────> turns + 256-dim voice embeddings  ──┐
                │                                                              │
                └─> Deepgram nova-3 ────> words → source_chunks (text)        │
                                                                               │
video (Scout)  ────> InsightFace @ 1 fps > face detections + 512-dim embeds  ─┤
                                                                               │
                                                                               ▼
                                                              Speaker Identification
                                                              (voice + face + fusion)
                                                                               │
                                                                               ▼
                                                              Knowledge Extraction
                                                              (claims, quotes, consensus)
```

| Stage | What it does | Surface spec |
|---|---|---|
| **Audio + video acquisition** | Scout downloads audio (and optionally video) to S3 — `audio_s3_key` populated; video staged ephemerally per request. | [ingestion.md](ingestion.md) |
| **Diarization (pyannote)** | `pyannote/speaker-diarization-3.1` segments audio into per-speaker turns; per-window 256-dim voice embeddings via `pyannote/wespeaker-voxceleb-resnet34-LM`. | This doc, step 1 |
| **ASR (Deepgram)** | `nova-3`, keyterm-biased to the canonical NRL roster; produces words + timestamps + paragraph breaks. | This doc, step 2 |
| **Merge** | Joins Deepgram utterances to pyannote turns by max-overlap; writes `source_documents` + `source_speakers` (one row per turn) + `source_chunks` (one row per utterance). | This doc, step 3 |
| **Speaker identification + fusion** | Per-turn voice match (sliding-window cosine vs `person_voiceprints`) + visual match (InsightFace + mouth-opening ASD vs `person_face_embeddings`) + cross-modal fusion → `source_speakers.speaker_person_id`. Plus face-track JSON for the review-UI overlay. | [speaker-identification.md](speaker-identification.md) |

## At a glance

| | |
|---|---|
| **Modules** | `services/api/app/analyst/transcribe.py` (orchestrator), `services/api/app/analyst/diarize.py` (pyannote stage). Speaker-identification modules — `identify_voice.py`, `visual_id.py`, `fusion.py` — are run inline by the orchestrator; see [speaker-identification.md](speaker-identification.md). |
| **Driver** | `python -m app.analyst.transcribe_cli <source_id>` · `make transcribe SOURCE_ID=<uuid>` |
| **Crew counterpart** | [Analyst](../crew/analyst.md) — Analyst's first surface, sitting in front of cleaning / claim extraction. |
| **ETL role** | **Transform.** Reads Scout's audio (and video, when speaker ID is in scope); produces the structured transcript artefacts every later stage depends on. |
| **Cost** | Deepgram ~$0.30 per 90-min video (nova-3 batch, words only). Pyannote 3.1 + InsightFace combined: ~50 min CPU per 45-min source locally; ~3 min wall time on the SageMaker Async GPU endpoint when `LINEUP_REMOTE=1`. End-to-end **~$0.43/source** with remote GPU enabled. |
| **Status** | Diarization + ASR + merge + voice ID + visual ID + fusion all live. Single-source CLI shipped. Recurring drain job not yet built. |

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
4. **Speaker identification (voice + face + fusion)** — see [speaker-identification.md](speaker-identification.md). The voiceprint and face registries are matched against each pyannote turn's per-window voice embeddings and (when a video stream is available) per-frame face embeddings; results are fused per turn into `speaker_person_id` + `match_method` + `match_confidence`. With empty registries every turn stays unidentified — no error.

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
- [Voice Identification (Phase 3)](speaker-identification.md) — successor surface that populates `speaker_person_id` from the embeddings this pipeline produces
- [Speaker Identification plan](../../todo/speaker-identification-plan.md) — Phase 1 ✅, Phase 2 ✅, Phase 3 ✅, Phase 4 (visual + fusion) next
- [Migration 044](../../../packages/db/migrations/044_audio_first_extract.sql) (chunks rebuilt with speaker FK), [Migration 045](../../../packages/db/migrations/045_split_ingestion_transcription.sql) (status fields split), [Migration 046](../../../packages/db/migrations/046_chunk_paragraph_break.sql) (paragraph_break), [Migration 047](../../../packages/db/migrations/047_pyannote_diarization.sql) (voice embeddings on source_speakers), [Migration 048](../../../packages/db/migrations/048_person_voiceprints.sql) (voiceprint registry)
