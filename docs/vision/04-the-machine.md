---
tags: [area/architecture]
---

# The Machine

> Created: 2026-05-25. Restructured as a layer-by-layer walkthrough of the system, from source discovery to presentation.

## Core thesis

You are building a system that turns messy public commentary into structured intelligence:

> Who said what, what does the crowd believe, who was right, who was early, and what should we pay attention to now?

NRL is the first domain. The reusable platform can later apply to AI, sport more broadly, finance, politics, entertainment, or any area where public claims and predictions matter.

What follows is the machine, layer by layer. Each layer is a component defined by what goes in and what comes out, how reusable it is across domains, and where it sits strategically — build now, build carefully, or park.

---

## 1. Source Discovery Layer

**Component:** Miner

**Purpose:** Find the relevant voices, sources, and content worth ingesting.

**Inputs**

- YouTube channels
- podcasts
- social media accounts
- newsletters
- articles
- press conferences
- interviews
- forums / fan communities
- official club or league sources

**Outputs**

- source registry
- creator / pundit registry
- source quality score
- ingestion priority
- topic relevance
- content freshness
- emerging voices
- new content to ingest

**Reusability**

High. You can point Miner at NRL, AI, SuperCoach, cricket, markets, or any other topic.

**Strategic status**

Useful internal infrastructure. Probably not a standalone product, because research-agent / source-discovery tooling is crowded. The defensible part is domain tuning, source scoring, and integration into the rest of the system.

See [Miner](../agents/crew/miner/README.md).

---

## 2. Data Ingestion Layer

**Component:** Ingestion Pipeline

**Purpose:** Pull raw content into the system — media *and* structured data feeds.

**Inputs**

- videos
- audio
- posts
- articles
- captions
- comments
- thumbnails
- metadata
- links
- JSON data feeds (fixtures, stats, ladders, injuries)
- scraped HTML pages (historical archives)

**Outputs**

- raw media files
- transcripts
- raw structured captures (JSON / HTML)
- typed projections into structured tables
- source metadata
- timestamps
- provenance records
- content IDs
- content type classification

**Reusability**

Very high. This is a generic "topic data ingestion" layer.

**Strategic status**

Necessary foundation, but not the main differentiator. The durability discipline behind it — archive everything, make every projection re-derivable from the archive — is documented in [data-lineage](../architecture/data-lineage.md). This is Miner's **bronze layer**: raw capture for every external source, media and structured alike, landed faithfully before any interpretation — see [Miner charter §D1](../agents/crew/miner/charter.md#d1-the-boundary-principle--miner-owns-the-bronze-layer).

---

## 3. Identity and Attribution Layer

**Component:** Lineup

**Purpose:** Identify who is speaking, appearing, or being referenced.

**Subcomponents**

- speaker diarisation
- speaker attribution
- face embeddings
- voice embeddings
- person registry
- alias registry
- nickname mapping
- known-person database
- human-in-the-loop correction
- confidence scoring

**NRL examples**

- "Critta" → Stephen Crichton
- "Turbo" → Tom Trbojevic
- "Madge" → Michael Maguire
- Polynesian player names handled correctly
- journalists, ex-players, coaches and podcasters recognised across appearances

**Outputs**

- speaker-attributed transcript
- person profiles
- aliases
- known faces
- known voices
- attribution confidence
- reviewed / unreviewed status

**Reusability**

High. This generalises to any domain with recurring public figures.

**Strategic status**

Very important. This becomes one of the compounding data assets — the registry only gets richer with every source ingested. See [entity-roles](../concepts/entity-roles.md) for the identity model it rests on.

---

## 4. Transcript Quality Layer

**Component:** Domain-Aware Transcript Cleaning

**Purpose:** Clean transcripts using domain-specific vocabulary and context.

**Handles**

- names
- nicknames
- clubs
- stadiums
- positions
- injuries
- suspensions
- competitions
- media personalities
- slang
- common phrases
- acronyms
- tactical terms

**Outputs**

- cleaned transcript
- corrected entities
- normalised names
- uncertain terms flagged
- transcript quality score

**Reusability**

High. The same pattern works for AI, finance, medicine, law, sport, etc. The vocabulary changes, but the method generalises.

**Strategic status**

Important quality multiplier. Better transcripts improve everything downstream.

---

## 5. Maintained Knowledge Layer

**Component:** Self-Maintaining Wiki / Domain Memory

**Purpose:** Maintain durable structured knowledge instead of re-deriving it from scratch every query.

**Entities tracked**

- people
- teams
- organisations
- shows
- topics
- narratives
- injuries
- contracts
- predictions
- claims
- events
- unresolved issues

**Outputs**

- living entity pages
- structured profiles
- current state summaries
- historical state changes
- evidence-backed updates
- unresolved questions
- stale information flags

**Reusability**

Very high. This can power NRL, AI, personal research, business intelligence, or any domain where knowledge rots quickly.

**Strategic status**

Core platform layer. The value is not "a wiki" — it's *maintained domain memory*. The novelty is not the wiki itself, but the maintenance discipline: near-zero-cost continuous upkeep, the bookkeeping humans abandon wikis over. See the [LLM Wiki pattern](../pages/wiki/llm-wiki-pattern.md).

---

## 6. Claim Extraction Layer

**Component:** Claims Engine

**Purpose:** Extract meaningful claims, predictions, rumours, and assertions from attributed content.

**Claim types**

| Claim type | Example | Trackability |
|---|---|---|
| Prediction | "Broncos will make the grand final" | High |
| Selection claim | "They'll pick him at fullback" | High |
| Injury timeline | "He'll miss six weeks" | High |
| Signing rumour | "He is going to the Roosters" | Medium/High |
| Evaluation | "He is a top-five halfback" | Medium |
| Tactical claim | "Their edge defence is the issue" | Medium |
| Vibe claim | "They don't look hungry" | Low |
| Historical fact | "They haven't won there since 2018" | High |

**Outputs**

- claim text
- speaker
- source
- timestamp
- claim type
- topic
- entity links
- confidence score
- specificity score
- verifiability score
- resolution criteria
- expected resolution date

**Reusability**

Very high. This is one of the true core capabilities.

**Strategic status**

Core intelligence layer. Without this, the system is just a media aggregator.

---

## 7. Consensus Layer

**Component:** Consensus Engine

**Purpose:** Track what the crowd collectively believes.

**Tracks**

- consensus view
- minority view
- contrarian view
- consensus drift
- sentiment shift
- topic heat
- narrative emergence
- narrative decay
- expert-vs-public divergence
- media-vs-market divergence

**Example outputs**

- "Most pundits are down on Souths."
- "Consensus is shifting towards the Warriors as a finals threat."
- "A small group of historically accurate analysts disagree with the mainstream view."
- "The market is more bullish than the media."

**Reusability**

Extremely high. Works anywhere with many public opinions.

**Strategic status**

Core differentiator. This is different from track record. Track record asks, *"Who was right?"* Consensus asks, *"What does the ecosystem believe?"* The powerful intersection is finding people who go *against* consensus and are *right*. Specced in [consensus-engine](../todo/consensus-engine.md).

---

## 8. Verification Layer

**Component:** Referee

**Purpose:** Determine whether claims resolved as true, false, partially true, unresolved, or unverifiable.

**Data sources**

- match results
- player stats
- team lists
- injury reports
- judiciary reports
- contract announcements
- ladder positions
- betting markets
- official statements
- media reports
- historical databases

> These all arrive through Miner's bronze layer — nrl.com match-centre, casualty-ward, ladder, and rugbyleagueproject feeds are Miner-acquired and trust-resolved per [Miner charter §D11](../agents/crew/miner/charter.md#d11-trust-hierarchy--which-source-wins-per-field). The Referee *reads* them; it does not fetch them.

**Outputs**

- claim outcome
- evidence
- resolution date
- confidence score
- dispute status
- manual review flag
- impact on speaker record

**Claim statuses**

| Status | Meaning |
|---|---|
| True | Clearly resolved as correct |
| False | Clearly resolved as incorrect |
| Partially true | Directionally right but not exact |
| Unresolved | Not enough time has passed |
| Unverifiable | Too vague or subjective |
| Disputed | Conflicting evidence |
| Cancelled | Premise changed before resolution |

**Reusability**

High, but domain-specific data integrations are required.

**Strategic status**

Essential. This is where credibility is won or lost. Verification only works where claims *resolve cleanly* — sport supplies that almost uniquely; AI supplies it only for the gradeable slice.

> **"Verification" here means outcome resolution** — did the prediction come true. Distinct from the Analyst `verify` pass ([charter §A7](../agents/crew/analyst/charter.md)), which is extraction-faithfulness QA — did we capture the claim correctly from the transcript. Two jobs that share a word: this layer grades *reality*; the Analyst pass grades the *extraction*.

---

## 9. Reputation Layer

**Component:** Scorecard

**Purpose:** Track the performance of claim-makers over time.

**Tracks**

- accuracy
- calibration
- specificity
- originality
- difficulty
- topic expertise
- contrarian correctness
- recency-weighted performance
- claim volume
- confidence-adjusted score
- domain-specific strengths

**Example profiles**

- "Strong on team selection."
- "Good on injuries, weak on match predictions."
- "Often early on young talent."
- "High-volume, low-specificity commentator."
- "Excellent when disagreeing with consensus."

**Reusability**

Very high. This is useful in sport, AI, finance, politics, technology, and media.

**Strategic status**

Core differentiator. But it should be built carefully — a crude accuracy leaderboard will be misleading. Realised today as the Alignment Index; see [The Ledger](../pages/ledger/overview.md).

---

## 10. Decision Layer

**Component:** Decision Worker

**Purpose:** Turn intelligence into recommended actions.

**Inputs**

- claims
- consensus
- track records
- market data
- constraints
- user goals
- risk tolerance
- current assumptions

**Outputs**

- ranked actions
- rationale
- assumptions
- confidence
- invalidation triggers
- alternative options

**NRL / SuperCoach examples**

- "Trade Player A to Player B."
- "Avoid this popular move."
- "Captain this player."
- "This recommendation breaks if team lists change."
- "This analyst's view matters because they are strong on team selection."

**Reusability**

High, but later-stage.

**Strategic status**

Park it for now. This is the "act on it" layer. It should come after the data, claims, consensus, and reputation layers are reliable. Specced in [decision-worker](../todo/decision-worker.md).

---

## 11. Agent Layer

**Component:** Jaromelu

**Purpose:** Provide an intelligent interface over the whole system.

**Capabilities**

- answer user questions
- summarise the current state
- explain consensus
- identify sharp voices
- compare claims
- make predictions
- challenge weak narratives
- highlight unresolved claims
- generate reports
- suggest what to watch next

**Example outputs**

- "The media consensus is too negative on this team."
- "This claim is spreading, but mostly from low-reliability sources."
- "Three historically accurate people disagree with the dominant view."
- "This player's injury timeline is uncertain; the public narrative is ahead of the evidence."
- "The betting market and pundit consensus are diverging."

**Reusability**

Very high.

**Strategic status**

Important, but not the foundation. The agent is only useful once the underlying data is good.

> **Not to be confused with the Analyst crew member.** This layer is [Jaromelu](../agents/crew/jaromelu/README.md)'s integrated voice — the conversational [ask-me](../pages/ask-me/overview.md) surface. The *Analyst* crew member is the silver / interpretive layer (cleaning, extraction, semantic consensus) at layers 4, 6, and 7; it makes meaning but does not voice the final call ([Analyst charter §A1](../agents/crew/analyst/charter.md)).

---

## 12. Observability and Governance Layer

**Component:** Agent Audit / Workbench

**Purpose:** Track what the system did, why it did it, what it cost, and where it failed.

**Tracks**

- runs
- prompts
- tools
- costs
- latency
- errors
- source decisions
- extraction decisions
- verification decisions
- human corrections
- replay logs
- budget limits
- system bounds

**Reusability**

Very high.

**Strategic status**

High-value internal infrastructure. Probably not worth making a standalone product, because LLM observability is already crowded. But for your own system, it is essential — every agent runs on it. See [agent-audit](../agents/system/agent-audit.md).

---

## 13. Presentation Layer

**Component:** Visible Labour UX

**Purpose:** Show the system's work, not just the final answer.

**What users see**

- sources ingested
- claims extracted
- evidence trails
- speaker attribution
- consensus shifts
- confidence levels
- unresolved claims
- why a recommendation changed
- where humans reviewed outputs
- how the system reached its conclusion

**Reusability**

High as a design principle.

**Strategic status**

Not a module — a product philosophy. This matters because trust is central. The product should not feel like a black-box chatbot.

---

## 14. Synthetic Media Layer

**Component:** Voice / Face / Digital Clone Capability

**Purpose:** Eventually support generative media using collected voice, face, and identity assets.

**Potential uses**

- synthetic host
- digital analyst
- avatar presenter
- generated explainer clips
- personalised media summaries

**Strategic status**

Future only. Do not make this a core pillar yet. It creates legal, ethical, and reputational risk, especially with public figures. The [content-production pipeline](../content-production-pipeline.md) already frames cloning as future, not required for launch — treat it accordingly.

---

## The simplified architecture

The cleanest high-level model is:

```
DISCOVER → INGEST → ATTRIBUTE → CLEAN → REMEMBER → EXTRACT → CONSENSUS → VERIFY → SCORE → ASK → PRESENT
```

---

## The crew / worker crosswalk

The Machine cuts the system by **pipeline stage**. The [crew](../agents/crew/README.md) cuts the *same* system by **cognitive mode** (research, analysis, skepticism, math, memory); the [system workers](../agents/system/README.md) cut it by **runtime process**. These are orthogonal cuts — you can't derive one from another — so this table reconciles them. A blank crew cell marks an infrastructural layer with no cognitive-mode owner.

Build state is *not* duplicated here. Worker status lives in the [system index](../agents/system/README.md); task-level state lives in [docs/build](../build/TASKS.md).

| # | Layer | Crew mode | Runtime (worker / surface) |
|---|---|---|---|
| 1 | Source Discovery | [Miner](../agents/crew/miner/README.md) | [source-discovery](../agents/system/source-discovery.md) |
| 2 | Data Ingestion | [Miner](../agents/crew/miner/README.md) | [ingestion](../agents/system/ingestion.md) |
| 3 | Identity & Attribution | — | [speaker-identification](../agents/system/speaker-identification.md) |
| 4 | Transcript Quality | [Analyst](../agents/crew/analyst/README.md) | [transcription-pipeline](../agents/system/transcription-pipeline.md) |
| 5 | Maintained Knowledge | [Archivist](../agents/crew/archivist/README.md) | [publishing](../agents/system/publishing.md) |
| 6 | Claim Extraction | [Analyst](../agents/crew/analyst/README.md) | [extraction](../agents/system/extraction.md) |
| 7 | Consensus | [Analyst](../agents/crew/analyst/README.md) | [publishing](../agents/system/publishing.md) |
| 8 | Verification | [Critic](../agents/crew/critic/README.md) | [decision](../agents/system/decision.md) |
| 9 | Reputation / Scoring | [Bookkeeper](../agents/crew/bookkeeper/README.md) | [decision](../agents/system/decision.md) |
| 10 | Decision Worker | [Jaromelu](../agents/crew/jaromelu/README.md) · [Critic](../agents/crew/critic/README.md) | [decision](../agents/system/decision.md) |
| 11 | Agent | [Jaromelu](../agents/crew/jaromelu/README.md) | [ask-me](../pages/ask-me/overview.md) |
| 12 | Observability | — | [agent-audit](../agents/system/agent-audit.md) |
| 13 | Presentation / UX | [Jaromelu](../agents/crew/jaromelu/README.md) | [the Feed](../pages/feed/layout.md) |
| 14 | Synthetic Media | — | [avatar](../avatar/system.md) |

What the crosswalk makes visible: the five crew modes fan out across all 14 layers and several layers (Identity, Observability, Synthetic Media) have *no* crew owner because they're plumbing, not thinking. The crew is the lens for *how Jaromelu reasons*; The Machine is the lens for *what the pipeline does*. Neither replaces the other.

**Medallion cross-reference.** Miner's charter cuts the same system a third way — by *data maturity*. In medallion terms: **bronze** is raw external capture, owned by Miner — layers 1–2 plus the structured feeds behind layers 8–9; **silver** is the interpretive transform owned by the Analyst — cleaning and claim extraction (layers 4, 6), plus the speaker→Person attribution slice of layer 3; **gold** is the curated and derived tier owned by the Bookkeeper and Archivist — consensus, scoring, the wiki (layers 5, 7, 9). The charter's medallion model names only those four crew; Critic (verification) and Jaromelu (decision, agent, presentation) are later crew that consume *across* all three tiers rather than owning one. See [Miner charter §D1](../agents/crew/miner/charter.md#d1-the-boundary-principle--miner-owns-the-bronze-layer).

---

## Related

- [Knowledge Asset](03-knowledge-asset.md) — the asset these layers build
- [Venture Thesis](01-venture-thesis.md) — why NRL is the proving ground, not the product
- [Agents](../agents/README.md) — the crew / system / skills taxonomy the crosswalk maps onto
- [Miner](../agents/crew/miner/README.md) — source discovery in practice
- [Agent Audit](../agents/system/agent-audit.md) — the observability layer + event model contract
- [LLM Wiki](../pages/wiki/llm-wiki-pattern.md) — the self-maintaining knowledge layer
- [The Ledger](../pages/ledger/overview.md) — the reputation layer (Alignment Index) in practice
- [Entity Roles](../concepts/entity-roles.md) — the identity model the registry rests on
- [Data Lineage](../architecture/data-lineage.md) — the forensic capture discipline behind ingestion
