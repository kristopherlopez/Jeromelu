---
tags: [area/agents, subarea/crew]
---

# Analyst — Jaromelu's Cross-Reference Mode

> **Charter & boundary (2026-05-23).** Analyst's largest *current* surface — **Lineup** (transcript materialisation + speaker identification) — is being moved **out of this repo** into an external service per [charter A2](charter.md#a2-lineup-is-a-service-boundary-not-a-sub-module). What remains is Analyst's durable identity: **the interpretive layer** — turning a speaker-attributed transcript into *meaning* (cleaning, embedding, claim/quote extraction, cross-source consensus). The in-repo Lineup code (`diarize.py`, `identify_voice.py`, `visual_id.py`, `fusion.py`, the GPU stack) is **legacy** — kept working, not extended ([charter A8](charter.md#a8-disposition-of-the-in-repo-lineup-code--legacy-not-deleted)). Decisions A1–A8 in [charter.md](charter.md); architecture in [architecture.md](architecture.md); forward plan in [roadmap.md](roadmap.md).

**Internal function** — the **interpretive layer**: it turns a speaker-attributed transcript into meaning. In medallion terms Analyst is **silver** (see [charter A1](charter.md#a1-the-boundary-principle--analyst-owns-the-interpretive-layer)):

1. **Cleaning, embedding, entity / quote / claim extraction, cross-source consensus + contradiction detection** — Analyst's durable scope. Cross-references claims across sources, finds contradictions, detects consensus shifts, builds structured evidence on top of the transcript. Skill-driven today; workerised per [roadmap Track 2](roadmap.md#track-2--interpretive-pass-buildout).

The structural transform that *produces* that transcript — **Lineup** (transcript materialisation + speaker identification: pyannote diarization, Deepgram ASR, voice/face/fusion) — currently lives in this repo but is **moving to an external service** ([charter A2](charter.md#a2-lineup-is-a-service-boundary-not-a-sub-module)); the in-repo code is legacy ([charter A8](charter.md#a8-disposition-of-the-in-repo-lineup-code--legacy-not-deleted)). Surface specs: [transcription](../../system/transcription-pipeline.md) · [identification](../../system/speaker-identification.md). It answers *who said what* (structural); Analyst answers *what it means* (interpretive).

**Not a separate visible character.** When this mode is active, Jaromelu's voice (and the UI activity status) reflects it.

**Internal tonal mode:** Precise, measured, intellectually honest. Presents both sides, highlights where the tension is — but doesn't resolve it. Resolution belongs to Jaromelu's integrated voice when he commits.

|                       |                                                                                                                                                              |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Type**              | Crew mode (internal reasoning)                                                                                                                               |
| **ETL role**          | **Transform — interpretive / silver.** Reads a speaker-attributed transcript; produces structured knowledge (cleaned text, embeddings, claims, consensus). The *structural* transform (audio→transcript) is Lineup, externalising ([charter A2](charter.md#a2-lineup-is-a-service-boundary-not-a-sub-module)). |
| **Scope (durable)**   | The interpretive layer: cleaning, chapter detection, annotation, embedding, entity/quote/claim extraction, cross-source consensus + contradiction detection. Skill-driven today; workerised per [roadmap Track 2](roadmap.md#track-2--interpretive-pass-buildout). |
| **Scope (legacy, externalising)** | Transcript materialisation (Deepgram words + pyannote turns) + Lineup speaker identification (voice + face + fusion). Moving to an external service ([charter A2](charter.md#a2-lineup-is-a-service-boundary-not-a-sub-module)); in-repo code frozen ([charter A8](charter.md#a8-disposition-of-the-in-repo-lineup-code--legacy-not-deleted)). Phase ledger: [Lineup status](#lineup-status) below. |
| **Code**              | `services/api/app/analyst/`. **Legacy (Lineup, externalising — [charter A8](charter.md#a8-disposition-of-the-in-repo-lineup-code--legacy-not-deleted)):** transcription (`transcribe.py`, `diarize.py`, `keyterms.py`), speaker ID (`identify_voice.py`, `visual_id.py`, `fusion.py`), clustering (`face_clusters.py`, `face_runs.py`, `voice_cluster_*.py`, `identity_alignment.py`), remote GPU (`remote.py`, `video_staging.py`, `services/gpu/`), enroll/CLI helpers. **Durable surface:** cleaning / extraction / consensus — skill-driven today (see [Pipeline position](#pipeline-position)), workerised under [roadmap Track 2](roadmap.md#track-2--interpretive-pass-buildout). |
| **Trigger**           | Manual CLI: `python -m app.analyst.transcribe_cli <source_id>` runs everything end-to-end. Recurring drain job for `transcription_status IS NULL` sources is on the backlog.            |

---

## Pipeline position

Scout drops audio in S3. Analyst picks it up and produces every downstream derivative. Today only the first derivative — the diarised transcript — is implemented.

```
Scout                       Analyst                                           Bookkeeper / Critic / Jaromelu
(audio in S3)         →     (transcript → claims → consensus)            →   (numbers + challenge + voice)
```

| Stage | What | Status |
|---|---|---|
| Transcribe | Deepgram nova-3 (words+timestamps, no diarize) + pyannote diarization + keyterm. Writes `source_documents` + `source_speakers` (with voice embeddings) + `source_chunks`. | Shipped 2026-05-03 |
| **Lineup — speaker ID** | Voice voiceprints + face embeddings + mouth-opening ASD + cross-modal fusion → `source_speakers.speaker_person_id` + `match_method` + `match_confidence`. Per-turn audio_match / visual_match provenance preserved. | Phases 1–4b-display shipped 2026-05-04. Phase 4b-action (click-to-reassign) shipped 2026-05-05. Compounding (Phase 5) now out-of-scope under externalisation ([charter A2](charter.md#a2-lineup-is-a-service-boundary-not-a-sub-module)). See [Lineup status](#lineup-status). |
| Clean | Fix garbles, merge restarts, normalise filler. Writes `source_documents.cleaned_text`, `source_chunks.clean_text`. | Skill-driven today (`/clean-transcript`); workerised version pending |
| Embed | OpenAI / Voyage embeddings → `source_chunks.embedding`. (Distinct from the voice/face embeddings Lineup writes — those live on `source_speakers` / `person_voiceprints` / `person_face_embeddings`.) | Not built |
| Extract claims / quotes | LLM extraction over chunks. Writes `quotes`, `claims`, `claim_chunks`. | Skill-driven today (`/process-transcript`); workerised version pending |
| Cross-reference / consensus | Detect contradictions and consensus shifts across sources. | Not built |

---

## Behavioural Rules

In Analyst mode, Jaromelu's voice:
- presents evidence for and against, fairly
- highlights contradictions explicitly
- detects and reports consensus shifts
- quantifies where possible ("2 sources agree, 1 contradicts")
- never makes the final call — that's the integrated Jaromelu voice
- flags confidence levels on cross-referenced claims

## Voice — Jaromelu in Analyst mode

Tone: precise, measured, both-sides. Sounds like a research analyst briefing a decision maker.

Example lines:

> "Cross-referencing complete: 2 sources bullish on Munster, 1 bearish. The bearish case cites the bye schedule."

> "Consensus shift detected: the market turned bearish on Cleary since Tuesday. 3 sources moved."

> "Contradiction: KingOfSC says buy Hynes, NRLBrothers says sell. Both cite matchup data but draw opposite conclusions."

> "Evidence is thin on this one. Only 1 source, low confidence."

These are out-of-mode for the **transcription** surface — Analyst's transcription pass is purely structural (audio → text + speakers), no editorialising. The voice lines above belong to the cross-reference pass once it's built.

---

## Hand-off contract — what Analyst writes today

The transcription pass writes:

| Table | Fields written | Fields left for later passes |
|---|---|---|
| `source_documents` | `s3_key`, `raw_text`, `transcript_available`, `language`, `checksum`, `chunk_count` | `cleaned_text` (cleaning pass) |
| `source_speakers` | `speaker_label` (e.g. `SPEAKER_00`), `start_ts`, `end_ts`, `embedding` (256-dim wespeaker), `embedding_model`, plus Lineup provenance: `audio_match_person_id` + `audio_match_score`, `visual_match_person_id` + `visual_match_score`, `match_method`, `match_confidence`, `speaker_person_id` (the fused answer). | — |
| `source_chunks` | `raw_text`, `chunk_index`, `start_ts`, `end_ts`, char offsets, `speaker_segment_id` (FK to pyannote turn it overlaps most), `paragraph_break` | `clean_text`, `embedding` |
| `person_voiceprints` | One row per sliding-window voice embedding from each enrollment span. Built up over time per host. | — |
| `person_face_embeddings` | One row per ArcFace face embedding from each enrollment frame. | — |
| `sources` | `transcription_status='transcribed'`, `extraction_method='deepgram_words+pyannote_v1'`, `diarization_method='pyannote-3.1'`, `video_format` (from Lineup format heuristic) | — |

It does **not** write `source_chapters` (analyse-transcript / chapter detection), `source_annotations`, `quotes`, `claims`, or `claim_chunks`. Those are subsequent Analyst passes.

---

## Lineup status

Lineup is the speaker-identification surface within Analyst's transcript materialisation pipeline. The detailed phase-by-phase plan, evaluation results, and tuning notes live in [docs/todo/speaker-identification-plan.md](../../../todo/speaker-identification-plan.md). Operator-facing details (enrollment, thresholds, how matching runs) live in [docs/agents/system/speaker-identification.md](../../system/speaker-identification.md). The summary:

| Phase | Scope | Status |
|---|---|---|
| **1** — Pyannote side-by-side | A/B pyannote 3.1 vs Deepgram diarizer on real podcast audio. | ✅ Shipped 2026-05-03. 83.6 % agreement with Deepgram; pyannote chosen. |
| **2** — Pyannote + voice embeddings | Replace Deepgram diarize with pyannote turns; ECAPA/wespeaker embeddings (256-dim) on every `source_speakers` row. | ✅ Shipped 2026-05-03. |
| **3** — Voice enrollment + identification | `person_voiceprints` registry; `enroll-voice` CLI; sliding-window k-NN + majority-vote matching. | ✅ Shipped 2026-05-03. 92.9 % precision on the audited source. |
| **4a** — Visual ID + fusion | Scout video acquisition; InsightFace face detection + 512-dim ArcFace; `person_face_embeddings` registry; voice/face fusion table on `source_speakers`. | ✅ Shipped 2026-05-03. |
| **4-asd** — Mouth-opening ASD heuristic | Per-frame "active speaker" picked by `landmark_3d_68` inner-mouth opening; per-turn density gate at 30 %. | ✅ Shipped 2026-05-04. Visual precision 55 % → 77 %. |
| **4b-display** — Review-UI overlay | HTML5 `<video>` + canvas face-box overlay coloured by `match_method`. Read-only. | ✅ Shipped 2026-05-04. |
| **4b-display-v2** — Ephemeral video + canvas-on-iframe overlay | Stop persisting per-source video. `video_staging.staged_video` yt-dlps into a 24 h-lifecycle staging key, deletes after `visual_identify` returns. `YouTubeFaceOverlay` draws bboxes on the YouTube iframe directly. | ✅ Shipped 2026-05-05. |
| **5.5** — Remote GPU inference | `services/gpu/` SageMaker Async endpoint (us-east-1, `ml.g5.xlarge`) hosting pyannote + InsightFace. ~50 min CPU → **~3 min** wall time when `LINEUP_REMOTE=1`. | ✅ Shipped 2026-05-05. |
| **4b-action** — Click-to-reassign | Click a face box → Person picker modal → writes face + voice embeddings + corrects `speaker_person_id`. | ✅ Shipped 2026-05-05. See [Manual reassign](../../system/speaker-identification.md#manual-reassign) for the endpoint sequence. |
| **5** — Cross-modal compounding | Periodic job auto-promotes high-confidence `voice+face` turns into the registries with `created_by='auto-confirmed'`. The mechanism that grows accuracy without operator effort. | ⛔ Out-of-scope under externalisation ([charter A2](charter.md#a2-lineup-is-a-service-boundary-not-a-sub-module)) — the compounding mechanism becomes the external service's concern, not this repo's. Was the only pending in-repo item. |

Flagged but not currently scoped:

- **Real audio-sync ASD** (Light-ASD / TalkNet / LoCoNet) to close the remaining ~23 % visual precision gap on reaction-shot false positives. Models aren't pip-packaged — vendoring exercise.
- **S-norm voice calibration** — bumps voice-precision ceiling once multiple hosts are enrolled.
- **Recurring drain job** over `transcription_status IS NULL AND ingestion_status='collected'` — currently single-source CLI.

---

## System-side counterpart

Analyst mode spans:

- **[Transcription](../../system/transcription-pipeline.md)** — current shipped surface (Deepgram words + pyannote diarization)
- **[Identification (Lineup)](../../system/speaker-identification.md)** — voice + face fusion, enrolment CLIs, threshold tuning
- **[Extraction](../../system/extraction.md)** — claim / entity resolution, cleaning, augmenting (skill-driven today)
- **[Publishing](../../system/publishing.md)** — `update_consensus_snapshots` for consensus shifts and contradictions (planned)

## Related

- [Charter](charter.md) — locked design decisions A1–A8, the Lineup boundary, risks, cost/testing/rollout
- [Architecture](architecture.md) — pipeline position, hand-off contract, the pass chain, current-vs-target architecture
- [Roadmap](roadmap.md) — status and the two-track forward plan (Lineup externalisation + interpretive-pass buildout)
- [Crew Dynamics](../dynamics.md) — Analyst mode's place in Jaromelu's internal reasoning flow
- [The Wiki](../../../pages/wiki/overview.md) — where cross-referenced knowledge surfaces, authored by Jaromelu
- [Speaker Identification plan (Lineup)](../../../todo/speaker-identification-plan.md) — full phase ledger, evaluation results, threshold tuning notes
- [Extraction method](../../../sources/extraction-method.md) — Deepgram parameters, keyterm vocabulary, cost model for the transcription pass
