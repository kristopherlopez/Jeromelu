# 2.2 Publishing Worker

**Phase:** 2 — Prove the Character (Personality + Experience)
**Priority:** 8 — Jaromelu gets personality
**Service:** `services/worker-publishing`

## Tasks

- [ ] Live feed event generation — convert system state changes into feed events
- [ ] Event types: `source_ingested`, `opinion_extracted`, `narrative_shift`, `prediction`, `trade_decision`, `match_review`
- [ ] Jaromelu voice layer — LLM characterisation to write in Jaromelu's voice
- [ ] Tone/temperature control (straight, sharp, lightly roasting)
- [ ] Display modes: thought, action, system, prediction, review
- [ ] Immutable event hashing for audit trail
- [ ] Temporal workflow: `PublishingWorkflow`
