---
tags: [area/operations, data-catalogue]
---

# Data Catalogue

Personal reference for the Jaromelu data model. Source of truth: `packages/shared/jeromelu_shared/db/models.py`

The schema breaks into five layers:

- **Identity** — typed per-kind tables for things claims/predictions/wiki reference: `people`, `player_attributes`, `people_roles`, `rounds`. Pre-mig-038 this was a single polymorphic `entities` table — now retired.
- **Structured world** — Real things and their facts: teams, venues, fixtures, rosters, injuries, per-round stats.
- **Content & claims** — Pipeline from channel → source → document → overlays → quote → claim, plus time-series popularity sidecars.
- **Reasoning & output** — What Jaromelu produces from the world plus the content: predictions, decisions, remarks, alignment scores, knowledge base, wiki. Cross-type subjects modelled as typed-FK association junctions (`claim_associations`, etc.).
- **Agent audit** — Per-run and per-event observability for Claude-Agent-SDK-based agents.

---

## Schema Overview

```
Layer 1 — IDENTITY ─────────────────────────────────────────────────────────────
   ┌──────────────┐        ┌────────────────────┐        ┌──────────────┐
   │    people    │──────▶ │ player_attributes  │        │    rounds    │
   │  (humans —   │   │    │       (SCD-2)      │        │  (NRL fixt.  │
   │   players,   │   │    └────────────────────┘        │   round id)  │
   │   coaches,   │   │                                  └──────────────┘
   │   etc.)      │   │    ┌────────────────────┐
   └──────────────┘   └──▶ │   people_roles     │
                           │ (multi-valued      │
                           │   role tenure)     │
                           └────────────────────┘

Layer 2 — STRUCTURED WORLD ─────────────────────────────────────────────────────
       ┌────────┐  ┌────────┐  ┌─────────┐  ┌──────────────────┐  ┌──────────┐
       │ teams  │  │ venues │  │ matches │──│ match_team_lists │  │ injuries │
       └────────┘  └────────┘  └─────────┘  └──────────────────┘  └──────────┘
            ▲                       ▲           ▲                      ▲
            └─────── home_venue_id ─┘           │                      │
                                                player_id ──▶ people  ─┘
                                                ▲
                                    ┌────────────────────┐
                                    │   player_rounds    │
                                    │  (SC overlay,      │
                                    │  FK→match,team)    │
                                    └────────────────────┘

Layer 3 — CONTENT & CLAIMS ─────────────────────────────────────────────────────
   scout_candidates           ──(promote)──▶ channels / sources    (Scout's review queue)
   scout_presenter_candidates ──(confirm)──▶ source_presenters     (Presenter Scout's queue)
                                              │
                                              └─▶ people  (created on confirm if no link)
   channels ──▶ sources ──▶ source_documents
      │           │              ├──▶ source_chunks       (atomic caption-level segments)
      │           │              ├──▶ source_speakers     (diarised turns)
      │           │              ├──▶ source_chapters     (semantic chapters)
      │           │              ├──▶ quotes  ─────────┐
      │           │              └──▶ claims  ◄────────┘
      │           │                     │
      │           │                     ├──▶ claim_chunks   (N:M with source_chunks)
      │           │                     └──▶ claim_associations  (typed-FK subjects)
      ▼           ▼
   channel_metrics   video_metrics       (time-series popularity sidecars)

Layer 4 — REASONING & OUTPUT ───────────────────────────────────────────────────
   predictions ──▶ prediction_associations   ──▶ outcomes
   decisions   ──▶ decision_associations     ──▶ outcomes ──▶ events
   consensus_snapshots                    plans
   remarks ──▶ remark_reactions           alignment_scores
   knowledge_base                         wiki_pages ──▶ wiki_revisions
   squad_slots  (planned)                 squad_trades  (planned)

Layer 5 — AGENT AUDIT ──────────────────────────────────────────────────────────
   agent_runs ──(run_id)──▶ agent_events    (per-run summary + per-event trail)
```

`*_associations` tables are typed-nullable-FK + CHECK exactly-one junctions. Each row points at one of `person_id` / `team_id` / `match_id` / `venue_id` / `round_id` — replaces the old polymorphic `subject_entity_id` UUID. See [refactor-entities-to-typed-tables](../refactor-entities-to-typed-tables.md) for the full design rationale (executed in migrations 036–038).

---

## Tables

### 1. Identity

The noun layer. People, rounds — the things claims, predictions, decisions, wiki pages, etc. reference.

- [people](people.md) — every human actor (players, coaches, advisors, commentators, journalists, referees)
- [player_attributes](player_attributes.md) — SCD-2 of slow-changing per-person facts (team, position, height/weight, contract)
- [people_roles](people_roles.md) — SCD-2 of role tenure per person (multi-valued at a single point in time)
- [rounds](rounds.md) — NRL/NRLW round identity for round-level claims/predictions/decisions

### 2. Structured world

Real-world rows holding facts. Cross-type references from claims/predictions/etc. point here via the typed FK columns on association junctions.

- [teams](teams.md) — every team across all grades (NRL, NRLW, NSW Cup, QLD Cup, junior pathway)
- [venues](venues.md) — stadium reference table
- [matches](matches.md) — fixture / result spine (one row per game across all grades)
- [match_team_lists](match_team_lists.md) — versioned named-17 announcements per match per team
- [injuries](injuries.md) — append-on-change timeline of player injury / suspension state
- [player_rounds](player_rounds.md) — per-player SuperCoach performance overlay (~60 columns)

### 3. Content & claims

Pipeline from channel → source → document → overlays → quote → claim, plus time-series popularity sidecars and Scout's review queues.

- [scout_candidates](scout_candidates.md) — Scout's candidate inbox (channels + videos awaiting approval)
- [scout_presenter_candidates](scout_presenter_candidates.md) — Presenter Scout's staging inbox
- [source_presenters](source_presenters.md) — confirmed `(channel, person, role)` association
- [channels](channels.md) — registry of content sources (YouTube, podcast, web, twitter, instagram)
- [channel_metrics](channel_metrics.md) — time-series popularity per channel (multi-platform via JSONB)
- [sources](sources.md) — individual content items (a specific video, episode, article)
- [video_metrics](video_metrics.md) — time-series popularity per video
- [source_documents](source_documents.md) — full transcript or text content for a source
- [source_chunks](source_chunks.md) — atomic caption-level segments (1:1 with deduped auto-caption segments)
- [source_speakers](source_speakers.md) — diarised speaker turns over a document
- [source_chapters](source_chapters.md) — semantic chapters detected over a document
- [quotes](quotes.md) — direct quotes extracted from source documents, attributed to a speaker
- [claims](claims.md) — every assertion or annotation pulled from a transcript span
- [claim_chunks](claim_chunks.md) — N:M junction linking claims to the source chunks they were extracted from
- [claim_associations](claim_associations.md) — polymorphic many-to-many between claims and typed entities

### 4. Reasoning & output

What Jaromelu produces from the world (Layer 2) plus the content (Layer 3).

- [predictions](predictions.md) — forecasts about future events, linked to evidence claims
- [prediction_associations](prediction_associations.md) — polymorphic many-to-many between predictions and typed entities
- [consensus_snapshots](consensus_snapshots.md) — aggregated claim sentiment for a typed subject at a point in time
- [decisions](decisions.md) — action decisions made in the system (trades, captain picks, etc.)
- [decision_associations](decision_associations.md) — polymorphic many-to-many between decisions and typed entities
- [outcomes](outcomes.md) — scored results for predictions and decisions after events occur
- [events](events.md) — immutable audit trail of system activity (hashed for tamper detection)
- [plans](plans.md) — strategy documents per round
- [remarks](remarks.md) — planned: opinionated, voiced analytical pieces with open → locked → resolved lifecycle
- [remark_reactions](remark_reactions.md) — planned: audience reactions to open/locked Remarks
- [alignment_scores](alignment_scores.md) — planned: prediction accuracy tracking per person
- [knowledge_base](knowledge_base.md) — distilled, structured knowledge chunks embedded for RAG retrieval
- [wiki_pages](wiki_pages.md) — prose per-entity (or per-channel) knowledge pages
- [wiki_revisions](wiki_revisions.md) — per-section edit log for wiki pages
- [squad_slots](squad_slots.md) — planned: SuperCoach squad management (squad_slots + squad_trades)

### 5. Agent audit

Per-run and per-event observability for Claude-Agent-SDK-based agents (Scout, Scribe, Analyst, Stats, Fixtures). Live-queryable store while a run is in flight; the same events also serialise to JSONL and upload to S3 at run end. See [docs/agents/system/agent-audit.md](../../agents/system/agent-audit.md) for the full audit pattern.

- [agent_runs](agent_runs.md) — run-level summary (one row per run, keyed by `run_id`)
- [agent_events](agent_events.md) — per-event audit trail (dense `sequence` per run for ordered replay)

---

## Other

- [deprecated](deprecated.md) — tables removed by migrations and what replaced them (`entities`, `entity_roles`, `player_attributes`, `player_team_history`, `source_annotations`)
- [migrations](migrations.md) — landmark migrations and how to keep this catalogue in sync when schema changes land
