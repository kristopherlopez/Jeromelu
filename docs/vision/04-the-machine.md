---
tags: [area/architecture]
---

# The Machine

> Created: 2026-05-25. Restructured around a two-tier reusable-component model.

[Knowledge Asset](03-knowledge-asset.md) argued that the *shape* of what Jaromelu builds is domain-agnostic. This doc decomposes the machine that builds it into **reusable components** — units defined by a contract (what goes in, what comes out), not by the product they happen to serve.

This is a *component* decomposition, deliberately not a product catalogue. Whether any component is worth selling is a separate question this doc ignores on purpose. The only questions here are: what is the reusable unit, what is its contract, what is generic versus domain-specific, and what is the seam already cut or still to cut.

The components sort into **two tiers that differ by radius of reuse**:

- **Tier 1 — Domain-blind infrastructure.** Reusable across *entirely different products*. These don't know what the NRL or a "claim" is; they'd drop into a support-agent or a legal-research tool unchanged. The deeper reuse — they travel furthest.
- **Tier 2 — Domain-pipeline components.** Reusable across *topics*, not products. Each is a generic engine plus an injected **domain pack** (lexicon, claim schema, resolution oracle, ontology). Swap the pack — NRL → AFL → AI — and the engine is untouched. The more valuable reuse — this is where the specific work lives.

The tiers also sit at opposite ends of "already extracted." Tier 1 is mostly **already factored** as shared code; making it reusable is mostly *lifting and naming*. Tier 2 is still **entangled** with NRL inside the skills; making it reusable is a real *refactor*. The [state table](#state-today--lift-vs-refactor) at the end is honest about which is which.

---

## The Stack at a Glance

```
  COMPOSITIONS         Accountability aggregator · Prediction agent · Generative media*
  (assembled from      ───────────────────────────────────────────────────────────────
   components)
  ───────────────────────────────────────────────────────────────────────────────────
  TIER 2               Knowledge/Wiki · Scoring · Consensus · Verification
  domain-pipeline      Claim Extraction · Identity · Attribution · Normalisation · Embeddings
  (engine + pack)      Assumption-Invalidation
  ───────────────────────────────────────────────────────────────────────────────────
  TIER 1               Agent Event Model  ← the spine
  domain-blind         Audit Harness · Streamed-Trace Transport · Agentic Discovery
  infrastructure       Forensic Re-derivable Capture
  * quarantined — see Compositions
```

Tier 1 is the substrate everything runs *on*; Tier 2 is the pipeline that runs *on it*; Compositions are products *assembled from* both.

---

## Tier 1 — Domain-Blind Infrastructure

No domain pack. Generic by construction. The reuse radius is "any agent-built system."

| Component | Contract (in → out) | State today |
|---|---|---|
| **Agent event model** | agent activity → a typed event stream (`run_started`, `turn_started`, `tool_use`, `tool_result`, `text`, `server_block`, `turn_complete`, `bound_hit`, `error`, `run_ended`) | Live, but embedded inside the audit module rather than standing alone |
| **Audit harness** | wrap an agent loop → run summary + per-event trace + cost + enforced bounds | **Factored** — `jeromelu_shared.agent_audit`. The exemplar. |
| **Streamed-trace transport** | agent events → live step-stream to a client (NDJSON; no SSE / WebSocket / job queue) | Pattern in use for slow mutating endpoints |
| **Agentic discovery** | discovery brief + source adapters → scored, deduped candidate sources | Live for Scout (`scout_candidates`) |
| **Forensic re-derivable capture** | external source → idempotent durable archive (L2) → re-derivable projection (L3) | Live — the L1→L4 model |

**Agent event model** — the typed taxonomy of what an agent does, turn by turn. Not really code; a *contract*. It is the most leverage-dense thing in Tier 1 because of what hangs off it (next section). Defined today inside [agent-audit](../agents/system/agent-audit.md); should be lifted into its own shared contract.

**Audit harness** — one row per run (`agent_runs`), one row per event (`agent_events`), a forensic JSONL bundle in S3, cost derived from token + server-tool counts, and `AgentBounds` (turns / tool-calls / wall-clock / budget) enforced uniformly. This is what a reusable component looks like done right: every agent imports it, no per-agent reinvention. Zero domain knowledge. Full contract in [agent-audit](../agents/system/agent-audit.md).

**Streamed-trace transport** — streamed step events for endpoints too slow to block on, without standing up SSE/WebSocket/job infrastructure. It is the *live twin* of the audit log: the same events, streamed to a UI instead of persisted to a table.

**Agentic discovery** — find the content ecosystem for a topic via an agent with web tools, then score and dedup candidates against what's already ingested. Generic: the loop, the triage rubric, the dedup. Domain-ish: the brief, the per-source adapters, the relevance rubric. Depends on the audit harness (bounds + cost) and a candidate store. Today this is [Scout](../agents/crew/scout/README.md).

**Forensic re-derivable capture** — archive every external source durably and idempotently (the archive is forensic and never deleted), then project it into a queryable store that is *fully re-derivable from the archive*. "Capture everything now, compose richer later." A storage discipline, domain-blind. Full model in [data-lineage](../architecture/data-lineage.md).

### The event model collapses three components

The agent event model isn't just for audit. The *same* typed stream is:

- **persisted** → the audit harness writes it to `agent_events` + S3,
- **streamed** → the trace transport pushes it live to a UI,
- **emitted** → every agent (discovery included) produces it.

**One contract, three consumers.** Stabilise the event taxonomy once and the harness, the transport, and discovery's instrumentation all hang off it. That makes the event model the highest-leverage Tier-1 component — it's the seam the others attach to, not a leaf.

A note this resolves: "visible labour" — the design choice to show the crew's reasoning as the spectacle — is **not a component**. It's a *consumer* of this stream. The reusable thing underneath the philosophy is the event model + the transport; the theatre is a styling of their output.

---

## Tier 2 — Domain-Pipeline Components

Each is a generic engine + an injected domain pack. The reuse radius is "any topic that can supply a pack."

| Component | Contract (in → out) | Pack supplies | State today |
|---|---|---|---|
| **Attribution** | media (+ voiceprint registry) → speaker-tagged transcript + review queue | — | Live (`source_speakers`); being externalised as a service |
| **Normalisation** | raw transcript + lexicon → cleaned transcript | lexicon: terms, aliases, phonetic confusions | Entangled in the `clean-transcript` skill |
| **Embeddings** | media → voice / face vectors | — | Voice live (Deepgram/pyannote); face planned |
| **Identity registry** | vectors + observations → resolved person IDs; enroll / match | (identity seed) | Partial (`people`, `cluster_label`, entity-roles) |
| **Claim extraction** | cleaned + attributed transcript + claim schema → structured claims | claim taxonomy, entity types | Entangled in the `process-transcript` skill |
| **Consensus** | typed opinions (entity, stance, time) → consensus + contrarian scores + drift | stance taxonomy | Specced (todo) |
| **Verification** | claim + resolution oracle → verdict + evidence | the oracle | Partial (`predictions` / `outcomes`) |
| **Scoring** | verdicts keyed by identity → accuracy profiles | — | Live (Alignment Index, `alignment_scores`) |
| **Knowledge / self-maintaining wiki** | source + wiki + schema → maintained wiki (pages, cross-refs, contradiction flags) | wiki schema / ontology | Live-ish (the Wiki, `wiki_pages`) |
| **Assumption-invalidation detector** | a plan + the premises it rests on → fire when a premise changes | constraint model | Specced (inside the Decision Worker) |

Three of these deserve a note beyond the table:

- **Consensus** is *not* Scoring. Scoring asks "is this individual right?" Consensus asks "what does the crowd collectively think, where is the divergence, how is sentiment shifting?" — buy/sell/hold snapshots, `contrarian_score`, `consensus_score`, drift over time. The two compose into the sharpest signal in the stack: *who goes against consensus and is right* (Consensus × Scoring). Specced in [consensus-engine](../todo/consensus-engine.md).

- **Self-maintaining wiki** — the reusable unit is not "render entity pages," it's the **maintenance loop**: ingest a source, integrate it into existing pages, update cross-references, flag contradictions, log. The novelty is *near-zero-cost continuous maintenance* — the bookkeeping humans abandon wikis over. Domain-agnostic by construction; the pack is just the schema. Pattern in [llm-wiki](../pages/wiki/llm-wiki-pattern.md), realised as [the Wiki](../pages/wiki/overview.md).

- **Assumption-invalidation detector** — extracted deliberately from the (NRL-specific) Decision Worker. The move-generator and constraint model are domain-shaped, but *"watch a plan's premises and signal when they go stale"* is a clean, rare, reusable primitive. Specced inside [decision-worker](../todo/decision-worker.md).

---

## Compositions, Not Components

Products *assembled from* the components above. Named here so they aren't mistaken for more plumbing.

- **Accountability-ranked aggregator** — Identity + Scoring + Consensus + Knowledge/Wiki + a presentation layer. Differentiated because it ranks voices by *graded accuracy*, not just collects them.
- **The prediction agent (Jaromelu)** — a consumer of every component plus a generator of its own calls. Graded on the same rubric (Scoring) as everyone it ingests; foregrounded only once it demonstrably rivals the humans.
- **Generative media — *quarantined*** — voice/digital clones built from the per-person media the Identity registry accumulates. Kept behind its own boundary for consent/legal reasons *and* architectural hygiene (clone code must never reach into the analytical components). A downstream consumer of registry media, gated, never a peer. The [content-production pipeline](../content-production-pipeline.md) doc already tags this work "not required for launch / future / legal review needed" — treat it accordingly.

---

## The Domain Pack — the Tier-2 Contract

Tier 2 reuse hinges on one artifact. A **domain pack** is the complete set of data a new topic supplies so the unchanged engines run on it:

| Pack component | Consumed by | NRL instance | Example: AI-tech |
|---|---|---|---|
| **Lexicon** — terms, aliases, phonetic confusions | Normalisation | player names, club nicknames, name garbles | model names, lab names, jargon |
| **Claim schema** — claim + entity types | Claim Extraction | SuperCoach claim types; player/team/round | capability & ship-date claims; model/lab/benchmark |
| **Resolution oracle** — ground truth + how to query it | Verification | nrl.com / SuperCoach results | benchmark leaderboards, release dates |
| **Stance taxonomy** — opinion poles | Consensus | buy / sell / hold | bullish / bearish / neutral |
| **Ontology** — the topic's entity graph | Knowledge / Wiki | teams, players, rounds, comps | labs, models, research areas |
| **Identity seed** *(optional)* — known persons | Identity registry | known NRL commentators | known AI commentators |

If a domain can supply these, Tier 2 runs on it without code change. **That is the test of whether the decomposition is real.** A caveat surfaced in the validity review: verification only works where claims *resolve cleanly* — sport supplies that almost uniquely; AI supplies it only for the gradeable slice. The pack shape is the same; the *quality* of the oracle is not.

---

## The Seams That Decide Reusability

1. **Two tiers, two radii — don't flatten them.** Tier 1 is reusable across products (domain-blind); Tier 2 across topics (pack-driven). Treating them as one flat "modules" list hides that they need different work and travel different distances.
2. **The event model is the Tier-1 spine.** One contract, three consumers (persist / stream / emit). Stabilise it and three components fall out of it.
3. **Domain-as-data is the Tier-2 spine.** Every Tier-2 engine takes its pack as injected data, never as branching code. The day `if sport == "nrl"` enters an engine, that component becomes a fork.
4. **Identity is the shared spine within Tier 2.** One registry; Attribution, Scoring, Consensus, and the aggregator all read it. Don't let each grow its own person table.
5. **The one cycle — Attribution ⇄ Registry — resolve by ownership.** Registry owns identities/embeddings; Attribution *proposes* enrollments back. Otherwise two embedding stores drift.
6. **Verification is asynchronous by nature.** "Claim now, verdict later" — durable pending-claim state + a per-domain trigger/oracle, designed up front, not bolted on.
7. **Contracts live in `packages/shared`.** The same separation-of-concerns rule the codebase already applies to generators: each component depends on the shared contract, not on its siblings. `agent_audit` already lives there — it's the template for where the rest of the contracts belong.

---

## State Today — Lift vs Refactor

For a component lens, the question that matters is "is the seam already cut?" Honest answer per component:

| Component | Tier | State | Work to make it reusable |
|---|---|---|---|
| Audit harness | 1 | Factored (shared) | None — it's the exemplar |
| Event model | 1 | Live, embedded in audit | **Lift** into its own shared contract |
| Streamed-trace transport | 1 | Pattern in use | **Lift** / generalise into shared |
| Agentic discovery | 1 | Live (Scout) | Generalise brief + adapters |
| Forensic capture | 1 | Live (L1→L4) | None — already a discipline |
| Attribution | 2 | Live, externalising | Hold the registry boundary |
| Scoring | 2 | Live | Keep it domain-blind |
| Knowledge / wiki | 2 | Live-ish | Extract the schema-driven loop |
| Identity registry | 2 | Partial | **Declare ownership** before a 2nd person table appears |
| Verification | 2 | Partial | Build async substrate + oracle interface |
| Normalisation | 2 | Entangled in skill | **Refactor** engine ⊥ lexicon |
| Claim extraction | 2 | Entangled in skill | **Refactor** engine ⊥ schema |
| Consensus | 2 | Specced | Build generic aggregator |
| Assumption-invalidation | 2 | Specced | Isolate from the move-generator |

Tier 1 is mostly *lift* (cheap — the seams are cut). Tier 2 is the real *refactor* — and the two skills (`clean`, `process`) are the load-bearing first step, since everything downstream depends on a clean engine/pack split.

---

## Related

- [Knowledge Asset](03-knowledge-asset.md) — the asset these components build; this doc is its engineering decomposition
- [Venture Thesis](01-venture-thesis.md) — why NRL is the proving ground, not the product
- [Agent Audit](../agents/system/agent-audit.md) — the Tier-1 audit harness + event model contract
- [Scout](../agents/crew/scout/README.md) — agentic discovery in practice
- [LLM Wiki](../pages/wiki/llm-wiki-pattern.md) — the self-maintaining knowledge component
- [The Ledger](../pages/ledger/overview.md) — Scoring (the Alignment Index) in practice
- [Entity Roles](../concepts/entity-roles.md) — the identity model the registry rests on
- [Data Lineage](../architecture/data-lineage.md) — the forensic L1→L4 capture component
