# 1.3 Extraction Worker

**Phase:** 1 — Prove the Brain (Intelligence Layer)
**Priority:** 4 — Turns raw text into structured knowledge
**Service:** `services/worker-extraction`

## Tasks
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
