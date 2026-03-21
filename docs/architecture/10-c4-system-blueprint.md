# C4-Style System Blueprint

This section describes Jeromelu using a C4-style structure: system context, containers, components, and cross-cutting concerns.

## Level 1 — System Context

### Primary System
**Jeromelu Platform**

A public AI-driven NRL SuperCoach experience that ingests ecosystem content, extracts structured intelligence, makes autonomous decisions, and publishes them through a character-led interface.

### Primary Actors

**Visitor / Fan**
- watches Jeromelu's feed
- explores team, predictions, and knowledge base
- asks SuperCoach questions
- compares their views against Jeromelu and the ecosystem

**Operator / Admin**
- approves and manages sources
- injects urgent events
- monitors workflows
- pauses decisioning or publishing if needed
- corrects entities and moderation issues

### External Systems

**Content Sources**
- YouTube channels
- podcast feeds
- websites and blogs
- radio transcripts where available
- manually added articles or transcripts

**SuperCoach / Match Context Sources**
- public NRL fixtures and match context
- SuperCoach-relevant schedule/context data
- later: player pricing/statistical sources

**LLM / AI Providers**
- used for extraction, synthesis, and character generation

**Notification / Scheduling Infrastructure**
- job scheduling and workflow execution
- internal alerts for failures or manual review

### System Context Diagram (textual)

```text
[Visitor / Fan]
    -> uses -> [Jeromelu Platform]

[Operator / Admin]
    -> manages -> [Jeromelu Platform]

[Content Sources]
    -> provide raw content to -> [Jeromelu Platform]

[Match / SuperCoach Context Sources]
    -> provide context to -> [Jeromelu Platform]

[LLM / AI Providers]
    -> provide model capabilities to -> [Jeromelu Platform]

[Scheduling / Workflow Infrastructure]
    -> triggers and runs jobs for -> [Jeromelu Platform]
```

## Level 2 — Container Diagram

The Jeromelu Platform should be split into a small number of high-value containers.

### 1. Web App / Public Experience
**Responsibilities**
- renders live feed
- renders war room
- renders team dashboard
- renders knowledge explorer
- renders prediction ledger and expert leaderboard
- hosts chat interface

**Users**
- visitors
- admins for lightweight operational views if desired

**Key properties**
- SEO-friendly shell
- dynamic modules for near-real-time updates
- should feel alive without full SPA complexity

### 2. API / Experience Backend
**Responsibilities**
- serves public frontend data
- serves chat responses
- exposes read models for feed, team, predictions, entities, experts
- handles auth for admin functions
- brokers requests to retrieval and publishing services

**Key properties**
- read-optimised for public views
- separates user-facing contracts from internal services

### 3. Workflow / Orchestration Service
**Responsibilities**
- scheduled job execution
- event-triggered workflow execution
- chaining workflows together
- retries, failure handling, audit logs

**Runs workflows such as**
- source discovery
- ingestion
- extraction
- consensus refresh
- strategy refresh
- weekly decisioning
- match review
- publish event generation

### 4. Ingestion Service
**Responsibilities**
- fetches raw content from approved sources
- stores full transcripts and article content
- normalises metadata
- chunks documents
- deduplicates by URL/checksum

### 5. Knowledge Extraction Service
**Responsibilities**
- entity extraction
- quote extraction
- speaker attribution
- claim extraction
- prediction extraction
- matchup extraction
- evidence packaging

### 6. Consensus & Decision Service
**Responsibilities**
- builds consensus snapshots
- computes candidate decisions
- maintains plans
- scores options via heuristics
- applies bounded contrarian rules
- produces rationale summaries

### 7. Publishing Service
**Responsibilities**
- transforms internal system events into public feed items
- manages public timeline objects
- updates prediction ledger
- updates team state projections
- applies voice layer to public-facing copy

### 8. Admin / Operator Console
**Responsibilities**
- source approval
- manual event injection
- entity correction
- moderation review
- workflow inspection
- pause decision engine
- pause publishing
- emergency kill switch

### 9. Relational Data Store
**Stores**
- sources
- documents
- entities
- quotes
- claims
- predictions
- consensus snapshots
- decisions
- plans
- events
- outcomes
- admin audit data

### 10. Vector Store
**Stores**
- embeddings for source chunks
- semantic retrieval index for Q&A and summarisation
- evidence retrieval support for generation

### 11. Object Storage
**Stores**
- raw transcripts
- cleaned documents
- exports
- archived artefacts
- possibly screenshots/media later

### Container Diagram (textual)

```text
[Visitor]
  -> [Web App]
  -> [API / Experience Backend]

[Operator]
  -> [Admin Console]
  -> [API / Experience Backend]

[Web App]
  -> [API / Experience Backend]

[API / Experience Backend]
  -> [Relational Data Store]
  -> [Vector Store]
  -> [Publishing Service]
  -> [Consensus & Decision Service]

[Workflow / Orchestration Service]
  -> [Ingestion Service]
  -> [Knowledge Extraction Service]
  -> [Consensus & Decision Service]
  -> [Publishing Service]

[Ingestion Service]
  -> [Content Sources]
  -> [Object Storage]
  -> [Relational Data Store]

[Knowledge Extraction Service]
  -> [LLM / AI Providers]
  -> [Relational Data Store]
  -> [Vector Store]

[Consensus & Decision Service]
  -> [Relational Data Store]

[Publishing Service]
  -> [Relational Data Store]
  -> [LLM / AI Providers]

[Admin Console]
  -> [API / Experience Backend]
```

## Level 3 — Component Diagram by Container

### A. Web App / Public Experience Components

#### Feed UI
- renders rewindable event stream
- groups thoughts, actions, predictions, reviews
- supports timeline browsing

#### War Room UI
- shows currently processed sources
- shows rising narratives and consensus movement
- shows candidate plans and active workflows in a user-friendly way

#### Team Dashboard UI
- public team
- trade history
- captain decisions
- round scores
- season progress

#### Knowledge Explorer UI
- player pages
- expert pages
- matchup pages
- quote evidence views
- prediction history views

#### Chat UI
- text-based advice entry
- team question input
- response thread rendering

#### Public Read Models
The frontend should consume denormalised read models, not raw relational joins.

Examples:
- feed_view
- team_dashboard_view
- expert_profile_view
- player_profile_view
- prediction_ledger_view

### B. API / Experience Backend Components

#### Feed Query API
- returns paginated feed events
- supports filters by event type, player, expert, round

#### Team Query API
- returns current squad, historical decisions, score summaries

#### Knowledge Query API
- returns pages for players, experts, matchups, source evidence

#### Prediction Query API
- returns Jeromelu and expert prediction histories and leaderboards

#### Chat Orchestrator
- accepts user questions
- retrieves structured facts and evidence
- passes evidence package to generation layer
- returns response plus optional cited evidence

#### Admin API
- authenticated controls for approvals, pauses, injections, corrections

### C. Workflow / Orchestration Service Components

#### Scheduler
- runs daily, weekly, and season workflows

#### Event Trigger Router
- reacts to source publication, manual events, match completion, and urgent changes

#### Workflow Runner
- executes workflow graphs
- tracks retries and status

#### Audit Logger
- persists run history, failure reasons, operator interventions

### D. Ingestion Service Components

#### Source Registry Reader
- reads approved source definitions and polling rules

#### Discovery Worker
- checks channels, feeds, and sites for new content

#### Fetch Worker
- pulls transcript/article data

#### Normaliser
- standardises metadata and cleaned text

#### Chunker
- breaks long transcripts into searchable chunks

#### Deduper
- prevents duplicate ingestion via URL/checksum/title matching

### E. Knowledge Extraction Service Components

#### Entity Extractor
- detects players, teams, experts, matchups

#### Quote Extractor
- identifies quote spans and likely speaker attribution

#### Claim Extractor
- maps text into buy/sell/hold and related SuperCoach claim types

#### Prediction Extractor
- captures future-oriented statements that can later be resolved

#### Lineage Binder
- attaches extracted artefacts back to source/chunk offsets

#### Embedding Builder
- generates embeddings for retrieval

#### Review / Validation Step
- checks schema validity
- checks evidence presence
- flags low-confidence extractions if needed

### F. Consensus & Decision Service Components

#### Consensus Aggregator
- groups claims by player/matchup/expert/time window
- computes buy/sell/hold counts and consensus score

#### Expert Accuracy Scorer
- resolves tracked predictions against outcomes
- updates leaderboard metrics

#### Candidate Generator
- creates possible trades, captain options, and strategy moves

#### Heuristic Scoring Engine
- scores options based on policy rules and current state

#### Contrarian Policy Engine
- selectively allows anti-consensus moves for drama within defined limits

#### Plan Manager
- stores and revises current round plans and scenarios

#### Decision Resolver
- finalises public action and rationale package

### G. Publishing Service Components

#### Event Builder
- turns internal state changes into immutable public events

#### Voice Renderer
- converts structured rationale into Jeromelu voice

#### Feed Publisher
- writes visible feed records and display payloads

#### Ledger Publisher
- updates prediction ledger and outcome records for public display

#### Team State Publisher
- updates public team state and explanatory summaries

#### Review Publisher
- posts postmortems after outcomes resolve

### H. Admin / Operator Console Components

#### Source Approval Panel
- review, approve, reject, disable sources

#### Manual Event Injection Panel
- create breaking news or contextual events

#### Entity Correction Panel
- merge aliases, fix misattributions, correct entities

#### Workflow Monitor
- inspect run status and errors

#### Publishing Controls
- pause feed output
- replay selected events

#### Decision Controls
- pause decision engine
- inspect pending recommendations

#### Emergency Controls
- kill switch
- disable public chat if needed

## Level 4 — Critical Internal Flows

These are the flows that matter most. They are the practical equivalent of the C4 component interactions.

### Flow 1 — Source Discovery to Public Thought

```text
Scheduler
 -> Discovery Worker
 -> Fetch Worker
 -> Normaliser
 -> Chunker
 -> Entity / Quote / Claim Extractors
 -> Lineage Binder
 -> Consensus Aggregator
 -> Event Builder
 -> Voice Renderer
 -> Feed Publisher
 -> Feed UI
```

Outcome:
A new source is ingested, claims are extracted, consensus shifts are detected, and Jeromelu publishes a new thought to the feed.

### Flow 2 — Weekly Decision Workflow

```text
Scheduler
 -> Plan Manager
 -> Candidate Generator
 -> Heuristic Scoring Engine
 -> Contrarian Policy Engine
 -> Decision Resolver
 -> Event Builder
 -> Team State Publisher
 -> Feed Publisher
 -> Team Dashboard UI / Feed UI
```

Outcome:
Jeromelu evaluates options, chooses a move, updates his public team, and logs the action immutably.

### Flow 3 — Expert Prediction Tracking

```text
Prediction Extractor
 -> predictions store
 -> match/outcome ingestion
 -> Expert Accuracy Scorer
 -> Ledger Publisher
 -> Prediction Ledger UI / Expert Page
```

Outcome:
The platform tracks what experts said, resolves outcomes later, and updates a public leaderboard.

### Flow 4 — User Q&A

```text
Visitor
 -> Chat UI
 -> Chat Orchestrator
 -> Knowledge Query API
 -> structured fact retrieval + vector retrieval
 -> generation with evidence package
 -> response returned to Chat UI
```

Outcome:
Jeromelu answers using structured knowledge and source-backed retrieval rather than freeform guessing.

### Flow 5 — Manual Breaking News Injection

```text
Operator
 -> Manual Event Injection Panel
 -> Admin API
 -> Event Trigger Router
 -> Plan Manager / Decision Service
 -> Event Builder
 -> Feed Publisher
```

Outcome:
The operator can inject urgent events and force plan reconsideration without waiting for the next scheduled cycle.

## Cross-Cutting Concerns

### 1. Evidence and Lineage
Every meaningful public statement should trace back to:
- source
- document
- chunk
- quote span
- extracted claim

This is the trust backbone.

### 2. Event Sourcing
Public actions should be written as immutable events.

Benefits:
- rewindable feed
- auditability
- replay
- stronger perceived autonomy

### 3. Separation of Internal vs Public State
Not all internal reasoning should be public.

Public:
- strategic reasoning
- evidence-backed summaries
- plans and actions

Private:
- operator controls
- confidence internals
- raw policy thresholds
- moderation state
- workflow/debug internals

### 4. Bounded Character Layer
Jeromelu's voice should sit at the publishing edge, not inside core decisioning.

Reason:
You do not want persona to contaminate extraction quality or decision logic.

### 5. Human Override Without Public Dependence
Operator controls must exist, but the product should not rely on constant manual puppeteering.

### 6. Read Models for Performance
Public experience should use denormalised read models built from core records.
This reduces frontend complexity and improves responsiveness.

## Deployment View

A sensible V1 deployment shape:

### Public Tier
- static frontend hosting
- dynamic API backend

### Application Tier
- API / experience service
- ingestion workers
- extraction workers
- publishing service
- decision service
- admin backend
- orchestration engine

### Data Tier
- relational database
- vector store
- object storage
- queue / message broker

### External Dependencies
- LLM provider(s)
- transcript/content providers where applicable
- optional alerting/monitoring services

## Recommended C4 Modelling Principles For This Project

1. Model the public experience separately from the intelligence engine.
2. Treat lineage as a first-class architecture concern, not a data detail.
3. Treat workflows as core architecture, not implementation plumbing.
4. Keep the character layer at the publishing boundary.
5. Optimise for auditability and replay from the beginning.

## Architecture Summary

In C4 terms, Jeromelu is:
- a **public-facing media intelligence platform** at system context level
- composed of **web, API, ingestion, extraction, consensus/decision, publishing, admin, and storage containers**
- built from **workflow-driven components** that transform raw media into structured intelligence and then into public events
- held together by **lineage, event logs, operator controls, and a character rendering layer**
