---
tags: [area/architecture]
---

# V1 Scope

## Delivered

- ✅ Approved source registry (whitelisted channels, admin add endpoint)
- ✅ Full transcript storage (S3 raw + DB-indexed `source_documents`)
- ✅ Rewindable live feed (The Feed, `/`)
- ✅ Agent-maintained knowledge base (The Wiki, `/wiki`)
- ✅ Prediction/outcomes surface (The Ledger scaffolding, `/ledger` — scoring WIP)
- ✅ Editorial content hub (The Analysis, `/insights`)
- ✅ Chat with the agent (Ask Me, `/ask` + inline in Feed)
- ✅ Admin controls (source approval, pipeline view, sync status, manual ingest)
- ✅ Immutable event log (`events` table with SHA256 dedup)
- ✅ Crew characters (Jaromelu, Scout, Analyst, Critic, Bookkeeper, Archivist)

## Outstanding

- Structured extraction pipeline (local experimentation — see [`todo/extraction-worker.md`](../todo/extraction-worker.md))
- Consensus snapshots + contrarian/consensus scoring
- Source-to-quote lineage surfaced in UI
- Rule-based decision engine (`worker-decision` not yet built)
- Alignment Index scoring (tables exist; scoring loop TBD)
- Expert/advisor accuracy leaderboard
- Speaker diarisation and attribution (post-MVP)

## Deferred

- Avatar video library (Kling generation)
- Voice (TTS / fine-tuned voice)
- Live game commentary
- Advanced simulation engine
- Price movement modelling
- Expected points distributions
- Broad NRL commentary outside SuperCoach

## Smallest Alive Version (historical — exceeded)

The original "smallest alive" bar was ingestion from 50+ approved sources, a visible thought/action feed, prediction ledger, and chat with no avatar. The live app exceeds this on most axes (five pages, multiple content surfaces) but source count and prediction scoring are still short of the bar.

---

# Recommended Build Roadmap

See [`todo/TODO.md`](../todo/TODO.md) for the detailed phase breakdown.

## Phase 1 — Prove the Brain (mostly done)

Built: source ingestion, transcript storage, consensus seed data, lineage groundwork. **Outstanding**: production extraction worker, consensus engine scoring.

Goal: make the intelligence layer real.

## Phase 2 — Prove the Character (mostly done)

Built: live feed, Jaromelu voice layer, rewindable timeline, public remarks. **Outstanding**: match review scoring loop, systematic prediction resolution.

Goal: make it feel alive.

## Phase 3 — Prove the Operator (in progress)

Built: admin interface skeleton, event logging. **Outstanding**: decision engine, Weekly Decision workflow, autonomous trade/captain calls.

Goal: make autonomy believable.

## Phase 4 — Prove Utility (not started)

To build: personalised Q&A, team comparison, premium advice pathways.

Goal: create monetisable value.

---

# Non-Negotiable Architectural Principles

1. Every important public claim needs lineage.
2. The feed is the product.
3. Near-real-time is enough.
4. Start with rules and heuristics, not a fake "AI genius" black box.
5. Use the character to dramatise real system state, not to cover weak architecture.
6. Store every public action as an immutable event.
7. Keep operator control strong and invisible.
8. Build the intelligence engine before the avatar.

---

# Success Criteria

Primary early metric:
Returning visitors.

Secondary metric:
Session length.

Qualitative success signals:
- social media sharing
- mentions in SuperCoach communities
- references in podcasts or YouTube channels
- people citing Jaromelu's takes unprompted

Failure signal:
Silence. No mentions means the architecture is not producing enough spectacle or value.
