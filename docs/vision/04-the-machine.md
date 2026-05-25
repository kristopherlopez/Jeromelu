---
tags: [area/architecture]
---

# The Machine

> Created: 2026-05-25.

[Knowledge Asset](03-knowledge-asset.md) argued that the *shape* of what Jaromelu builds is domain-agnostic — ingest a domain's sources, attribute claims to speakers, grade them against reality, remember. This doc takes the next step and cuts **the machine that builds the asset** into discrete modules.

Each module is defined by a **contract** (what goes in, what comes out), not by the product it happens to serve today. A module is reusable exactly when its interface doesn't leak the domain it was born in. NRL is not wired into the engines — it's a **data pack injected into them**. Get that one boundary right and "extends to any sport, likely any topic" stops being a slogan: the only thing rebuilt per domain is the pack, not the machine.

Most of what looks like "a different product" in conversation is one of three things here: a **module** (a reusable engine with a stable contract), a **composition** (a product assembled from modules), or a **data pack** (the domain knowledge a module consumes). Sorting them is the whole point of this doc.

---

## The Principle: Domain as Data

The failure mode is treating each capability as its own startup and forking the code per domain. The discipline that prevents it is simple to state and hard to hold:

> Every module takes its domain knowledge as **injected data** — a lexicon, a claim schema, a resolution oracle, an ontology — never as branching code.

When this holds, the NRL build is the *first caller* of a generic stack, not the stack itself. Standing up "the same thing for AFL" or "the same thing for AI-tech predictions" becomes the work of authoring a new pack and pointing the modules at it. When this breaks — when `if sport == "nrl"` creeps into an engine — every module quietly becomes a fork, and the platform thesis dies one conditional at a time.

The single contract that makes this real is the [domain pack](#the-domain-pack--the-contract-that-unlocks-reuse), specified at the end.

---

## The Stack at a Glance

Each layer consumes the one below it. Plumbing at the bottom, products at the top.

```
  COMPOSITIONS   Accountability aggregator · Prediction agent (Jaromelu) · Generative media*
                 ───────────────────────────────────────────────────────────────────────
  ANALYTICS      Knowledge Base ·  Track-Record Scoring
                 Claim Verification ·  Claim Extraction
                 ───────────────────────────────────────────────────────────────────────
  IDENTITY       Identity Registry  (the shared spine — everything keys off it)
                 ───────────────────────────────────────────────────────────────────────
  CAPTURE        Attribution ·  Normalisation ·  Embeddings
  * quarantined — see Compositions
```

| # | Module | Contract (in → out) | Domain knowledge, injected as data |
|---|--------|---------------------|-------------------------------------|
| 1 | **Attribution** | media (+ voiceprint registry) → speaker-tagged transcript + review queue | none — generic |
| 2 | **Normalisation** | raw transcript + lexicon → cleaned transcript | lexicon: terms, name aliases, phonetic confusions |
| 3 | **Embeddings** | media → voice / face vectors | none |
| 4 | **Identity Registry** | vectors + observations → resolved person IDs; enroll / match | none — people are rows, not code |
| 5 | **Claim Extraction** | cleaned + attributed transcript + claim schema → structured claims | claim taxonomy, entity types |
| 6 | **Claim Verification** | claim + resolution oracle → verdict + evidence | the oracle (match results, benchmark dates…) |
| 7 | **Track-Record Scoring** | verdicts keyed by identity → accuracy profiles | none |
| 8 | **Knowledge Base** | claims + entities → organised, queryable, rendered store | light topic ontology |

---

## The Modules

Each module below is scoped the same way: its contract, what it does, **what it is as its own product**, **how other products reuse it**, where it lives in Jaromelu today, and the **boundary to hold** to keep it reusable.

### 1. Attribution (Speaker-ID)

- **Contract** — `media (+ voiceprint registry) → speaker-tagged transcript + a review queue of low-confidence segments`
- **Scope** — Diarise audio/video, then *resolve* anonymous speakers to known identities using voiceprints. Emits confidence per segment and routes only the uncertain ones to a human — the "minimal HITL" loop. The product is not diarisation (commoditised); it's **diarisation + identity resolution + a calibrated review queue** that gets a usably-attributed transcript out the door with bounded human effort.
- **As its own product** — A "who-said-what" API for anyone with multi-speaker audio: podcast tooling, qualitative research, legal/medical transcription, media monitoring. Sold on *attribution accuracy per minute of human review*, not raw WER.
- **Reused by other products** — Any product needing speaker-attributed text: Claim Extraction is its primary consumer here; outside Jaromelu, a meeting-notes tool or a compliance-monitoring tool would consume the same contract unchanged.
- **In Jaromelu today** — The load-bearing dependency. Already being drawn as a **separate service**, end state an API that returns a speaker-attributed transcript (see [Knowledge Asset → What It Costs](03-knowledge-asset.md)). Speaker state lives in `source_speakers` with a `cluster_label` layer.
- **Boundary to hold** — Attribution *reads* the Identity Registry; it must not own its own private person store. It proposes enrollments back to the registry but never becomes a second source of truth for "who exists." (See [the cycle](#2-identity-is-the-shared-spine-not-a-per-product-leaf).)

### 2. Normalisation (Domain-Term Cleaning)

- **Contract** — `raw transcript + domain lexicon → cleaned transcript`
- **Scope** — Repair ASR output using a domain lexicon: real spellings of names, known aliases/nicknames, and the phonetic confusions auto-captions reliably produce. The reusable asset is **not** "NRL cleaning" — it's a generic corrector *plus* a method for mining a lexicon from a corpus. NRL is one lexicon; AI-tech is another; finance is another.
- **As its own product** — A domain-aware transcript-cleanup layer that sits on top of any ASR vendor. Most ASR is generic and mangles in-domain jargon and names — that gap is the product.
- **Reused by other products** — Drops in ahead of Claim Extraction for any domain; equally usable as a standalone "clean my industry transcripts" step for teams who never touch claims.
- **In Jaromelu today** — The [`clean-transcript`](../agents/skills/README.md) skill and [sources/cleaning](../sources/cleaning.md) patterns, driven by the player registry + NRL domain knowledge.
- **Boundary to hold** — The engine and the lexicon must be separate artifacts. Today the skill fuses corrector logic with NRL specifics; the refactor target is **generic corrector + pluggable lexicon** so a new domain is a data drop, not a code change.

### 3. Embeddings

- **Contract** — `media → voice and/or face vectors`
- **Scope** — Pure feature extraction: turn audio into voiceprints (pyannote/Deepgram) and faces into face vectors. Stateless and entirely domain-free.
- **As its own product** — The least defensible standalone (vendors exist); best treated as a thin, swappable adapter rather than a product to sell.
- **Reused by other products** — Feeds both Attribution (voiceprints) and the Identity Registry (the vectors it resolves on). Any biometric or media-search product reuses it.
- **In Jaromelu today** — Implicit inside the speaker-ID work; face embeddings are the planned addition that lets one identity be confirmed across voice *and* face.
- **Boundary to hold** — Keep it stateless and vendor-swappable. Embeddings are an input to the registry, never a store of identity themselves.

### 4. Identity Registry

- **Contract** — `vectors + observations → resolved person IDs; enroll / match / merge`
- **Scope** — The system of record for *people*: known persons, their accumulated voice/face embeddings, and the resolution logic that decides "this anonymous speaker is that known person" — across sources and across media types. This is where one person becomes traceable across many appearances.
- **As its own product** — A cross-media identity-resolution service: "is this the same person, here and here?" Valuable to media archives, rights management, and content discovery. (Note the privacy/consent surface — this is the module where it's sharpest.)
- **Reused by other products** — The **shared spine**. Attribution resolves against it; Scoring keys track records to it; the aggregator promotes people out of it; generative media draws its collected per-person media from it. Almost everything above touches it.
- **In Jaromelu today** — `people`, the [entity-roles SCD-2 model](../concepts/entity-roles.md) (one person, many roles over time), and the `cluster_label` layer that already points toward a single resolved identity store.
- **Boundary to hold** — One registry, everything reads it. The temptation is to let each product grow its own person table; resist it. Registry **owns** identities and embeddings; consumers **propose** enrollments. This resolves the one dependency cycle in the stack (Attribution needs voiceprints from the registry; the registry is fed by Attribution) by declaring ownership rather than duplicating state.

### 5. Claim Extraction

- **Contract** — `cleaned + attributed transcript + claim schema → structured claims (typed, time-stamped, entity-linked, speaker-attributed)`
- **Scope** — Mine unstructured commentary for claims, classify each by type, link it to the entities it's about, and stamp who said it and when. Multi-pass and verified before anything is trusted as load-bearing — garbage claims poison everything downstream.
- **As its own product** — A "claims API" over any opinion corpus: turn talk into a structured, queryable ledger of assertions. Useful well beyond prediction — market research, narrative tracking, discourse analysis.
- **Reused by other products** — Feeds Verification, Scoring, and the Knowledge Base. The claim schema is the injected domain knowledge: SuperCoach claim types for NRL, a different taxonomy for AI-tech.
- **In Jaromelu today** — The [`process-transcript`](../agents/skills/README.md) multi-pass pipeline; lands in `claims` / `quotes` / `source_chunks`.
- **Boundary to hold** — The taxonomy of "what counts as a claim" is data (part of the pack), not hard-coded extraction logic.

### 6. Claim Verification (Grading)

- **Contract** — `claim + resolution oracle → verdict (right / wrong / partial) + evidence link`
- **Scope** — Resolve predictions against reality when reality arrives. This is the **asynchronous** module — "claim now, verdict later" — and that temporal decoupling is a property to design for, not bolt on. Tracks a prediction lifecycle (open → locked → resolved) and grades only when the outcome is unambiguous, on an honest rubric.
- **As its own product** — The scarce, defensible piece. Anyone can collect predictions; *grading them rigorously and at scale, over time* is what almost nobody does. A "did this prediction come true?" engine is the heart of the moat.
- **Reused by other products** — Produces the verdicts Scoring aggregates. The **resolution oracle** is the injected domain knowledge: match results from the factual spine for NRL; benchmark scores / ship-dates for AI; price feeds for markets.
- **In Jaromelu today** — Grading against the nrl.com / SuperCoach factual spine; `predictions` / `outcomes` lifecycle, surfaced via [data-lineage](../architecture/data-lineage.md).
- **Boundary to hold** — Build it durable and trigger-driven from day one (pending claims awaiting resolution + a per-domain oracle), not as a synchronous transform. And never soft-grade — "well, technically" rots the authority of everything above it.

### 7. Track-Record Scoring (Alignment Index)

- **Contract** — `verdicts keyed by identity → accuracy profiles (overall + conditional)`
- **Scope** — Aggregate graded verdicts into per-person track records, sliced by *what they're good at* (tipping vs form reads vs injuries vs finals). Pure statistics over the layers below — calibration, hit-rate, conditional accuracy. Entirely domain-free.
- **As its own product** — A credibility-scoring layer for pundits/forecasters in any field. Answers the question no aggregator answers cleanly: **"who actually reads this well?"** Natural research adjacency to prediction and betting markets *(heavily regulated — an adjacency to approach carefully, not a casual feature)*.
- **Reused by other products** — Powers the aggregator's ranking and gives the prediction agent its own honest scorecard on the same rubric.
- **In Jaromelu today** — The Alignment Index in [the Ledger](../pages/ledger/overview.md); `alignment_scores`.
- **Boundary to hold** — Scoring consumes only `(identity, verdict)` pairs. It must stay ignorant of domain specifics — the moment it knows about NRL, it stops being reusable.

### 8. Knowledge Base

- **Contract** — `claims + entities → an organised, queryable, human-readable store`
- **Scope** — Organise everything captured into per-entity, navigable knowledge — and *render* it so the asset becomes something you can stand inside rather than a hidden database. Audit and trust are the same transparency seen from two sides.
- **As its own product** — An auto-maintained, source-linked knowledge base for any topic — distinct from generic LLM wikis because every statement is attributed and graded.
- **Reused by other products** — The presentation/retrieval surface any composition reads from; also the audit surface that keeps the upstream modules honest.
- **In Jaromelu today** — [The Wiki](../pages/wiki/overview.md), maintained by the Archivist; `wiki_pages`.
- **Boundary to hold** — The topic ontology is light and injected. The renderer is generic; what's rendered is data.

---

## Compositions, Not Modules

These are *products assembled from the modules above* — not reusable engines themselves. Naming them as compositions keeps them from being mistaken for more plumbing.

- **Accountability-ranked aggregator** — Identity Registry + Scoring + Knowledge Base + a presentation layer. The differentiated aggregator: it doesn't just collect voices, it **ranks them by graded accuracy**. That ranking is the hook that makes it non-generic — and it falls straight out of the modules, requiring no new engine.
- **The prediction agent (Jaromelu himself)** — A consumer of every module *plus* a generator that makes its own calls. The endgame, not the start: you earn the right to make predictions by first proving you can grade others'. He runs passively from day one and gets foregrounded only once his calls demonstrably rival the humans' on the same rubric.
- **Generative media — *quarantined*** — Voice clones today, digital clones later, built from the per-person media the Identity Registry accumulates. Kept behind its own boundary for two reasons: (1) consent/legal/reputational risk — cloning real public figures without consent could poison the credibility of the analytical product; (2) architectural hygiene — clone-generation code must never reach into the modules the credible analytics depend on. It is a *downstream consumer* of registry media, gated, never a peer of the analytical stack.

---

## The Seams That Decide Reusability

Listing modules is easy. These four boundaries are where reusability is actually won or lost.

1. **Domain knowledge is data, never code.** The whole thesis. Each module takes its pack (lexicon / claim schema / oracle / ontology) as injected data. The current skills (`clean`, `process`) fuse engine + NRL — the standing refactor target is *engine + pluggable pack*.
2. **Identity is a shared spine, not a per-product leaf.** One registry; Attribution, Scoring, the aggregator, and generative media all read it. Don't let each product grow its own person table.
3. **There is exactly one dependency cycle — Attribution ⇄ Registry — resolve it by ownership.** Registry owns identities/embeddings; Attribution is a consumer that *proposes* enrollments back. Otherwise two embedding stores drift apart.
4. **Verification is asynchronous by nature — design for it up front.** Every other module is a synchronous transform; Verification is "claim now, verdict later." Durable pending-claim state + a per-domain trigger/oracle from day one.

A fifth, practical seam: **module contracts belong in `packages/shared`** (the same separation-of-concerns rule the codebase already applies to generators). The interface is the shared artifact; each module depends on the contract, not on its siblings.

---

## What's Already Modular

The template already exists. **Speaker-ID (Attribution) is being drawn as a separate service** whose end state is an API returning a speaker-attributed transcript, with NRL as merely its first caller. That is exactly the pattern every other module should follow: a typed contract, domain knowledge injected, the current product just one consumer.

Replicate that template for Normalisation, Verification, and Scoring and the reusable spine is in place. NRL becomes one domain pack among future ones — not the thing the machine is made of.

---

## The Domain Pack — the Contract That Unlocks Reuse

Everything above hinges on one artifact. A **domain pack** is the complete set of data a new topic must supply for the unchanged machine to run on it:

| Pack component | Consumed by | NRL instance | Example: AI-tech |
|----------------|-------------|--------------|------------------|
| **Lexicon** — terms, name aliases, phonetic confusions | Normalisation | player names, club nicknames, Polynesian-name garbles | model names, lab names, jargon |
| **Claim schema** — claim types + entity types | Claim Extraction | SuperCoach claim types; player/team/round entities | capability claims, ship-date claims; model/lab/benchmark entities |
| **Resolution oracle** — the source of ground truth + how to query it | Verification | nrl.com / SuperCoach results feed | benchmark leaderboards, release dates, funding announcements |
| **Ontology** — the topic's entity graph for organising | Knowledge Base | NRL structure (teams, players, rounds, comps) | labs, models, research areas |
| **Identity seed** *(optional)* — known persons to bootstrap | Identity Registry | known NRL commentators | known AI commentators/forecasters |

If a new domain can supply these five, the eight modules run on it without code change. That is the test of whether the decomposition is real. The gating decision — and the thing to protect before more NRL leaks into the engines — is committing to this pack shape now, and refactoring the existing skills to consume it.

---

## What This Costs / Open Decisions

- **The skills need splitting.** `clean-transcript` and `process-transcript` are NRL-shaped today. Extracting engine-from-pack is real work and the prerequisite for everything here.
- **Identity store ownership** must be declared before a second person-table appears. It's cheap now, expensive after drift.
- **Verification's async substrate** is a design choice to make deliberately ([Temporal is not in prod](../temporal-notes.md); the simpler durable-queue + per-domain-oracle pattern is likely the right call).
- **The generative-media quarantine** is a decision to make explicit, not a default to drift into.
- **Media vs intelligence.** The deeper strategic fork — is the business the *audience* (aggregator, voices, attention) or the *verified track-record dataset* (intelligence, applications)? — is upstream of this doc and shapes which modules get hardened first. Worth resolving against [goals.yaml](../../README.md) before committing build order.

---

## Related

- [Knowledge Asset](03-knowledge-asset.md) — the asset these modules build; this doc is its engineering decomposition
- [Venture Thesis](01-venture-thesis.md) — why NRL is the proving ground, not the product
- [The Show](02-the-show.md) — the crew that operates the machine, made watchable
- [The Ledger](../pages/ledger/overview.md) — Track-Record Scoring in practice
- [The Wiki](../pages/wiki/overview.md) — the Knowledge Base, made visible
- [Entity Roles](../concepts/entity-roles.md) — the identity model the registry rests on
- [Data Lineage](../architecture/data-lineage.md) — the concrete L1→L4 capture model
