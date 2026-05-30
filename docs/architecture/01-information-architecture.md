---
tags: [area/architecture]
---

# Information Architecture

> **Where this data comes from:** see [`data-lineage.md`](data-lineage.md) for the end-to-end source → S3 → DB → app lineage covering every entity below — the canonical "what feeds what" map. **Column-level schema** for every table lives in the operations trinity ([data-catalogue](../operations/data-catalogue/README.md) + [data-lineage](../operations/data-lineage/README.md)). This doc holds the **conceptual** model only.

## Core Objects
The system revolves around structured entities:
- Source
- Episode / article / transcript
- Quote
- Claim
- Expert / Advisor
- Player
- Team
- Matchup
- Prediction
- Decision
- Event
- **Remark** — the atomic output unit; an opinionated, voiced analytical piece with an open→locked→resolved lifecycle
- Plan
- Outcome
- **Alignment Score** — per-entity prediction accuracy tracking for the Alignment Index
- **WikiPage / WikiRevision** — prose per-entity knowledge pages and their edit history (power [The Wiki](../pages/wiki/overview.md))
- **KnowledgeBase entry** — distilled, embedded content chunks for RAG (power [Ask Me](../pages/ask-me/overview.md))

### Real-world fixture spine

A parallel object cluster represents the games themselves, distinct from
the source/claim pipeline that feeds opinion content:

- **Venue** — stadium reference (capacity, surface, timezone)
- **Match** — one row per game across all grades (NRL, NRLW, NSW Cup, QLD Cup, …); home/away team, kickoff, status, scores
- **MatchTeamList** — versioned named-17 announcements per match per team (Tuesday list, Thursday list, late changes — all preserved as immutable versions)
- **Injury** — append-on-change timeline of player availability state, sourced from the NRL casualty ward and cross-referenced

The fixture spine is the join target for `PlayerRound` (the SuperCoach
overlay, deferred to V2) and is what powers the "games due to be played /
games played" query surface across the app.

## Lineage Principle
Every meaningful opinion or claim should trace back to the exact source words.

That means the system stores:
- raw transcript / raw article text
- source metadata
- extracted quote spans
- entity links
- derived opinions
- timestamps

Nothing important should exist without provenance.

## Public State
Visible to the audience:
- wiki pages (per-entity prose, continuously maintained by the Archivist)
- predictions, decisions, outcomes, remarks (open / locked / resolved)
- expert and source tracking
- consensus tracking
- event timeline (The Feed)
- alignment index (commentator leaderboard, audience scores, Jaromelu's record)
- crew activity — status and recent actions from all six crew members (Jaromelu, Miner, Analyst, Critic, Bookkeeper, Archivist; see [agents/crew/](../agents/crew/README.md))

## Private State
Internal only:
- candidate rankings
- orchestration status
- moderation flags
- confidence / uncertainty internals
- hidden operator controls
- system prompts and policies

---

# Data Model

The **conceptual** model is above. The **column-level schema** — every table, every column, with provenance — is deliberately **not** duplicated here, because hand-copied schema rots the moment a migration lands. It lives in the operations trinity, maintained against the live migrations:

- [`operations/data-catalogue/`](../operations/data-catalogue/README.md) — one file per DB table, column-level schema
- [`operations/data-lineage/`](../operations/data-lineage/README.md) — per-table source → S3 → extractor → column mapping
- [`data-lineage.md`](data-lineage.md) — the conceptual L1→L4 capture model that ties them together

Source of truth for the schema itself: `packages/db/migrations/` (applied via `make migrate`).
