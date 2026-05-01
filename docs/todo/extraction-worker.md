---
tags: [area/todo, status/planning]
---

# 1.3 Extraction Worker

**Phase:** 1 — Prove the Brain (Intelligence Layer)
**Priority:** 4 — Turns raw text into structured knowledge
**Service:** `services/worker-extraction`
**Status:** On hold — validating extraction approach locally first

## Design Decisions

- **Single-pass extraction** — one LLM call per document returns all extraction types (entities, quotes, claims, predictions) in one JSON response
- **Model choice** — cheap model via OpenRouter (MiniMax M2.5, Gemini 2.5 Flash, or similar). Final choice decided empirically after benchmarking on real transcripts. ~$0.01/doc target
- **Entity resolution** — LLM resolves against canonical NRL player list (~510 players, 17 teams) included in prompt. Aliases handled at extraction time, not as a separate step
- **Claim taxonomy** — coarse types (buy/sell/hold/captain/avoid/breakout/matchup_edge) plus structured attributes (sentiment_strength, time_horizon, reasoning_category). Will evolve through experimentation
- **Schema contract** — Pydantic models in `packages/shared` define extraction output shape. Separate from DB models. Used as validation in Claude Code skill and as reference for prompt design
- **Run tracking** — `extraction_runs` table tracks each batch (started_at, document_count, notes, is_production). FK `extraction_run_id` added to entities, quotes, claims, predictions tables

## Approach: Local Experimentation First

Production worker is on hold. Validate the extraction approach before building infrastructure.

### Phase A — Corpus & Ground Truth
- [ ] Backfill 500–1000 transcripts via ingestion worker
- [ ] Run strong LLM (Opus) on ~100 transcripts, human-review output → gold standard
- [ ] Spot-check LLM output on remaining transcripts → silver standard
- [ ] Explore traditional NLP techniques (NER, regex, keyword classifiers) to see what can be done cheaply

### Phase B — Local Extraction Tooling
- [ ] Python script to pull transcripts from DB and export for processing
- [ ] Define Pydantic extraction schema in `packages/shared`
- [ ] Claude Code skill to validate JSON extraction output and write to DB
- [ ] DB migration: `extraction_runs` table + `extraction_run_id` FK on output tables

### Phase C — Production Worker (after approach validated)
- [ ] Temporal workflow: `ExtractionWorkflow`
- [ ] Model-agnostic LLM call via OpenRouter
- [ ] Schema validation + retry/fallback on malformed output
- [ ] Write structured records to DB (entities, quotes, claims, predictions)
- [ ] Source lineage — link every claim back to exact quote and document
- [ ] Confidence scoring for all extractions

## Tasks (Original — preserved for reference)
- [ ] Entity extraction — identify players, teams, experts from text (LLM-powered)
- [ ] Entity resolution — link mentions to canonical entity records, handle aliases
- [ ] Quote extraction — find direct quotes with speaker attribution and text spans
- [ ] Claim extraction — classify opinions as buy/sell/hold/captain/avoid/breakout
- [ ] Prediction extraction — identify forward-looking claims with event windows
- [ ] Matchup extraction — team matchup narratives, injury context
- [ ] Confidence scoring for all extractions
- [ ] Source lineage — link every claim back to exact quote and document
- [ ] Write structured records to DB (entities, quotes, claims, predictions)
- [ ] Temporal workflow: `ExtractionWorkflow`

## Future (Post-MVP — moved from Ingestion Worker)

- [ ] Speaker diarization — download audio from S3, run Deepgram diarization, produce speaker-segmented transcript
- [ ] Speaker identification — match diarized "Speaker 1/2/3" labels to known expert entities
- [ ] Manual speaker annotation UI/endpoint — admin corrects speaker labels
- [ ] Audio sound byte extraction — slice audio clips aligned with transcript segments per speaker
- [ ] Voice asset pipeline — organised speaker audio clips for downstream use (voice cloning, content clips)
