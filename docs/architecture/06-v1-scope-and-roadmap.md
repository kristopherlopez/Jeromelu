---
tags: [area/architecture]
---

# V1 Scope

> V1 is **NRL commentary** — Jaromelu ingesting the NRL media ecosystem, forming opinions, making public calls, and getting graded against reality. SuperCoach gameplay (squad / trades / captain, price modelling) is the **deferred V2 overlay**, not V1. See [01 — Venture Thesis](../vision/01-venture-thesis.md) and [02 — The Show](../vision/02-the-show.md).

## Delivered

- ✅ Approved source registry (whitelisted channels, admin add endpoint)
- ✅ Full transcript storage (S3 raw + DB-indexed `source_documents`)
- ✅ Rewindable live feed (The Feed, `/`)
- ✅ Agent-maintained knowledge base (The Wiki, `/wiki`)
- ✅ Prediction/outcomes surface (The Ledger scaffolding, `/ledger` — scoring WIP)
- ✅ Chat with the agent (Ask Me, `/ask` + inline in Feed)
- ✅ Admin controls (source approval, pipeline view, sync status, manual ingest)
- ✅ Immutable event log (`events` table with SHA256 dedup)
- ✅ Crew (Jaromelu + Scout, Analyst, Critic, Bookkeeper, Archivist)

> The Analysis (`/insights`) editorial hub was also built, but is **deferred as a core V1 surface** — its useful pieces fold into the Feed and the Wiki's round pages. See [02 — The Show](../vision/02-the-show.md).

## Outstanding (the V1 build-out)

- Structured extraction at scale — the transcript-derived claims that make the opinion layer real (local experimentation today)
- Consensus snapshots + contrarian/consensus scoring
- Source-to-quote lineage surfaced in the UI
- The **Alignment Index** scoring loop (tables exist; scoring TBD) + the commentator accuracy leaderboard
- Speaker diarisation and attribution at scale — the load-bearing dependency for the opinion layer
- The **living-number heartbeat** — Remarks whose read moves as intel lands (see [02 — The Show](../vision/02-the-show.md))
- A rule-based decision engine (`worker-decision` not yet built)

## Deferred

- **SuperCoach gameplay (the V2 overlay)** — squad / trades / captain calls, price-movement modelling, expected-points distributions, squad submission and review
- Avatar video library (Kling generation) and voice (TTS / fine-tuned)
- Live in-game commentary
- Advanced simulation engine

## Smallest Alive Version (historical — exceeded)

The original "smallest alive" bar was ingestion from 50+ approved sources, a visible thought/action feed, a prediction ledger, and chat with no avatar. The live app exceeds this on surface count — but the parts that make it *bite* (extraction at scale, speaker attribution, the scoring loop) are still the real outstanding work.

---

# Recommended Build Roadmap

See [`todo/TODO.md`](../todo/TODO.md) for the detailed phase breakdown.

## Phase 1 — Prove the Brain (mostly done)

Source ingestion, transcript storage, lineage groundwork. **Outstanding:** extraction at scale, consensus scoring. Goal: make the intelligence layer real.

## Phase 2 — Prove the Character (mostly done)

Live Feed, Jaromelu's voice, rewindable timeline, public Remarks, visible crew. **Outstanding:** the living-number heartbeat, match-review scoring. Goal: make it feel alive — awe on arrival, aquarium on return.

## Phase 3 — Prove the Calls (in progress)

The Alignment Index doing its job: Jaromelu's calls graded against reality alongside the human pundits, until they *demonstrably rival* them. **Outstanding:** the scoring loop, systematic prediction resolution, the commentator leaderboard, the named rival. Goal: earn the credibility the awe is cashing.

## Phase 4 — Prove It Extends (not started)

The downstream directions on the same captured data: discovery (find the voices worth following), then the first real extension — **SuperCoach** as the V2 overlay; betting-signal research later. Goal: turn the asset into new directions. See [03 — Knowledge Asset](../vision/03-knowledge-asset.md).

---

# Non-Negotiable Architectural Principles

1. Every important public claim needs lineage.
2. The Feed is the product.
3. Near-real-time is enough — but the number must move when reality moves.
4. Start with rules and heuristics, not a fake "AI genius" black box.
5. Use the character to dramatise real system state, not to cover weak architecture.
6. Store every public action as an immutable event.
7. Keep operator control strong and invisible.
8. Build the intelligence engine before the avatar.

---

# Success Criteria

Primary early metric: returning visitors.
Secondary metric: session length.

Qualitative success signals:

- social sharing — receipts, bold calls that landed
- mentions in NRL commentary communities (and SuperCoach communities, as that audience overlaps)
- references in podcasts or YouTube channels — especially the named rival responding
- people citing Jaromelu's takes unprompted

Failure signal: silence. No mentions means the architecture isn't producing enough spectacle or value. (Operating-signals detail: [08 — Explainability & Governance](05-explainability-and-governance.md).)
