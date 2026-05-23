---
tags: [area/architecture]
---

# Runtime Architecture

## System Topology

### A. Source Discovery Layer
Purpose:
Find new candidate content.

Functions:
- poll known channels / feeds / sites
- discover new episodes or articles
- deduplicate by URL and checksum
- queue for approval or automatic ingestion

Output:
New source records.

### B. Source Approval Layer
Purpose:
Prevent garbage ingestion.

Modes:
- pre-approved source list
- admin approval queue for new creators / sites
- source health rules

This matters because bad inputs will poison the brand.

### C. Ingestion Layer
Purpose:
Fetch and store raw bytes. Extract-only — no interpretation.

Functions:
- audio acquisition (yt-dlp m4a → S3) for podcast / video sources
- low-res video acquisition (when visual identification is in scope)
- article extraction (when non-video sources are added)
- metadata capture
- raw byte storage

V1 rule:
Store the full raw audio (and video, where collected) permanently. The full
Deepgram + pyannote JSON artefacts are also retained so transcripts can be
re-merged from raw bytes without re-paying ASR cost.

Owned by **Scout** today (see
[../agents/crew/scout.md](../agents/crew/scout.md) §3.5 and
[../agents/system/ingestion.md](../agents/system/ingestion.md)). Article /
RSS / Twitter ingest is on the backlog; audio is the only live extractor.

### D. Transcription + Identification Layer
Purpose:
Turn raw audio into a structured, speaker-attributed transcript.

Functions:
- diarisation (`pyannote/speaker-diarization-3.1`) — turn-level segmentation with per-window voice embeddings
- ASR (Deepgram nova-3) — words, timestamps, paragraph breaks; keyterm-biased to the canonical NRL roster
- merge — joined utterances → `source_documents` + `source_speakers` (one row per pyannote turn) + `source_chunks` (one row per utterance)
- speaker identification — voice match (sliding-window cosine vs `person_voiceprints`) + visual match (InsightFace + mouth-opening ASD vs `person_face_embeddings`) + per-turn cross-modal fusion → `source_speakers.speaker_person_id`

Output:
fully diarised, optionally per-Person-attributed transcript chunks.

Owned by **Analyst** ([../agents/system/transcription-pipeline.md](../agents/system/transcription-pipeline.md),
[../agents/system/speaker-identification.md](../agents/system/speaker-identification.md)).
Heavy inference can offload to a SageMaker Async endpoint
([../../services/gpu/SETUP.md](../../services/gpu/SETUP.md)) when
`LINEUP_REMOTE=1`.

### E. Knowledge Extraction Layer
Purpose:
Turn structured transcripts into structured claims.

Functions:
- entity recognition
- quote extraction
- opinion / prediction / matchup extraction
- claim normalisation

Output:
quotes, claims, predictions, linked entities.

Skill-driven today (`/clean-transcript`, `/process-transcript`); the
workerised version is pending. Owned by Analyst once shipped.

### F. Knowledge Layer
Purpose:
Provide queryable state for the rest of the product.

Contains:
- relational store for structured facts
- vector store for semantic retrieval
- consensus snapshot builder
- expert performance history

### G. Decision Engine
**Status: not built.** `worker-decision` is unbuilt (see [08-technology-stack](08-technology-stack.md)); Jaromelu's calls are produced directly today. The shape below is the intended V1 design — rules + heuristics, not ML.

Inputs:
- consensus signals across ingested sources
- matchup narratives
- public stats / fixture context
- Jaromelu's prior calls and current standing positions

Outputs:
- candidate calls
- the call he commits to, with public-facing rationale
- deliberate contrarian calls when allowed

Important:
Contrarian behaviour should be policy-bounded, not random. It should only occur inside safe thresholds.

*(SuperCoach squad/trade decisions are a deferred V2 overlay on this same engine.)*

### H. Orchestration Layer
**Status: not in production.** Temporal exists in local dev only ([08-technology-stack](08-technology-stack.md)); production runs **cron jobs** and one-shot CLI invocations, not a workflow engine. The chain-of-workflows model below is the aspirational shape — see [04-workflow-architecture](04-workflow-architecture.md).

Supports (intended):
- scheduled jobs
- event-triggered jobs
- workflow-to-workflow triggering
- retries
- dead-letter queues
- audit logs

Typical flows:
1. discover source → ingest → extract → update consensus → publish a Remark
2. injury news → inject event → re-evaluate open calls → publish the update (the live-number heartbeat)
3. round window → form the call → lock it → resolve against the result

### I. Publishing Layer
Purpose:
Convert machine state into the public experience.

Produces:
- live Feed events (crew activity + Remarks)
- Wiki page updates (the Archivist)
- prediction Ledger updates (the Alignment Index)
- Ask Me chat answers

### J. Admin / Operator Layer
Needs on day one:
- source approvals
- manual event injection
- pause decision engine
- pause publishing
- replay event generation
- moderation queue
- entity correction / merge tools
- emergency kill switch

### K. Frontend Experience Layer
Recommended shape:
Mostly static website shell with dynamic modules.

Why:
- simpler to build
- easier SEO
- enough for near-real-time
- avoids overengineering early

Dynamic modules — the four surfaces:
- the Feed (`/`)
- the Wiki (`/wiki`)
- the Ledger (`/ledger`)
- Ask Me (`/ask`)
