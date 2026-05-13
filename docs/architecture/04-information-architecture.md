---
tags: [area/architecture]
---

# Information Architecture

> **Where this data comes from:** see [`data-lineage.md`](data-lineage.md) for the end-to-end source → S3 → DB → app lineage covering every entity below. That doc is the canonical "what feeds what" map.

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
- **KnowledgeBase entry** — distilled, embedded content chunks for RAG; also stores Analysis articles (power [Ask Me](../pages/ask-me/overview.md) and [The Analysis](../pages/analysis/overview.md))

### Real-world fixture spine

A parallel object cluster represents the games themselves, distinct from
the source/claim pipeline that feeds opinion content:

- **Venue** — stadium reference (capacity, surface, timezone)
- **Match** — one row per game across all grades (NRL, NRLW, NSW Cup, QLD Cup, …); home/away team, kickoff, status, scores
- **MatchTeamList** — versioned named-17 announcements per match per team (Tuesday list, Thursday list, late changes — all preserved as immutable versions)
- **Injury** — append-on-change timeline of player availability state, sourced from the NRL casualty ward and cross-referenced

The fixture spine is the join target for `PlayerRound` (the SuperCoach
overlay) and is what powers the "games due to be played / games played"
query surface across the app.

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
Visible to users:
- wiki pages (per-entity prose, continuously maintained by the agent)
- analysis articles (editorial content by round and type)
- predictions, decisions, outcomes, remarks (open / locked / resolved)
- expert and source tracking
- consensus tracking
- event timeline (The Feed)
- alignment index (expert leaderboard, user scores, Jaromelu's record)
- crew activity — status and recent actions from all six crew members (Jaromelu, Scout, Analyst, Critic, Bookkeeper, Archivist; see [agents/crew/](../agents/crew/README.md))

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

## Recommended Schema

### sources
- source_id
- source_type (youtube, podcast, web, radio, manual)
- title
- creator_name
- canonical_url
- approved_flag
- ingestion_status
- published_at
- ingested_at

### source_documents
- document_id
- source_id
- raw_text
- cleaned_text
- transcript_available
- language
- checksum
- chunk_count

### source_chunks
- chunk_id
- document_id
- chunk_index
- text
- start_offset
- end_offset
- embedding

### entities
- entity_id
- entity_type (player, team, advisor, coach, referee, commentator, journalist, matchup, round) — denorm of current primary role for people-typed entities
- canonical_name
- aliases
- slug
- metadata_json

### teams
Canonical roster of every team across all grades feeding into NRL plus NRLW.
Covers NRL, NRLW, NSW Cup, QLD Cup (Hostplus Cup), Jersey Flegg, Mal Meninga,
SG Ball, Cyril Connell, Harold Matthews. `parent_team_id` self-references
to wire a feeder team to its senior NRL/NRLW side; `entity_id` links senior
rows back into the canonical entities table so claims and predictions don't
duplicate identity.
- team_id
- slug (UNIQUE; e.g. `brisbane_broncos`, `norths_devils`, `brisbane_broncos_nrlw`)
- name, short_name, aliases
- grade (nrl, nrlw, nsw_cup, qld_cup, jersey_flegg, mal_meninga, sg_ball, cyril_connell, harold_matthews)
- competition (display string — NRL Premiership, NSW Cup, ...)
- parent_team_id (FK → teams, NULL for top grades)
- entity_id (FK → entities, UNIQUE, populated for NRL/NRLW rows)

Seeded from `data/teams.yaml` via `make seed-teams`. Junior pathway grades
are schema-allowed but not seeded yet — populate when current-season comp
lineups are confirmed.

### entity_roles (SCD-2)
Tracks role tenure so a single entity can carry multiple sequential or concurrent roles
(e.g. Andrew Johns: player → commentator; Michael Ennis: coach + commentator).
- entity_role_id
- entity_id (FK → entities)
- role (player, coach, commentator, journalist, referee, advisor)
- effective_from (DATE)
- effective_to (DATE, NULL = current)
- is_primary (drives the wiki page route; one current primary per entity, enforced by partial unique index)
- metadata_json (role-scoped: team for player, network for commentator, club for coach)
- source

See [Entity roles](../concepts/entity-roles.md) for worked examples and the role-transition pattern.

### wiki_pages
- page_id
- entity_id (FK → entities, nullable)
- channel_id (FK → channels, nullable)
- page_type (player, team, advisor, channel, round)
- slug (UNIQUE)
- title, content, summary, metadata_json, status
- exactly one of entity_id / channel_id is set per row (`ck_wiki_page_subject`)

Channel-typed pages describe the outlet (SC Playbook YouTube). Entity-typed
pages describe a person/team/round. The wiki index combines `advisor` and
`channel` pages under the **Voices** tab. See [Wiki overview](../pages/wiki/overview.md).

### quotes
- quote_id
- document_id
- chunk_id
- speaker_entity_id
- quoted_text
- start_offset
- end_offset
- said_at_reference
- confidence

### claims
- claim_id
- quote_id
- subject_entity_id
- claim_type (buy, sell, hold, captain, avoid, breakout, matchup edge)
- polarity
- strength
- effective_round
- extracted_at

### predictions
- prediction_id
- predictor_entity_id
- subject_entity_id
- prediction_type
- predicted_value_text
- event_window
- evidence_claim_ids
- created_at
- resolved_at
- resolution_status

### consensus_snapshots
- snapshot_id
- subject_entity_id
- time_bucket
- buy_count
- sell_count
- hold_count
- neutral_count
- contrarian_score
- consensus_score

### decisions
- decision_id
- decision_type (trade, captain, start_sit, squad_structure, article_topic, reply)
- subject_entity_id
- action_json
- rationale_summary
- strategy_tag
- created_at
- executed_at
- public_flag

### plans
- plan_id
- status
- round_number
- plan_summary
- scenario_json
- updated_at

### events
- event_id
- event_type
- related_entity_ids
- related_decision_id
- related_prediction_id
- display_text
- display_mode (thought, action, system, prediction, review)
- visibility
- created_at
- immutable_hash

### outcomes
- outcome_id
- prediction_id or decision_id
- actual_value_json
- result_label
- scored_at

### squad_slots, squad_trades (deprecated)
These tables were designed for the retired "My Squad" page — a personal SuperCoach roster surface. They remain in the schema but are not actively written or read by the live app. Retained for historical records and potential future use; not part of the current V1 feature set. See [pages/analysis/overview.md § History](../pages/analysis/overview.md).

### remarks
- remark_id
- voice_text (Jaromelu's voiced output)
- subject_entity_ids (players, teams, matchups referenced)
- position (buy, sell, hold, captain, avoid)
- conviction (low, medium, high)
- status (open, locked, resolved)
- evidence_claim_ids (upstream claims that built this remark)
- decision_id (link to the decision that produced it)
- resolution_json (outcome data once resolved)
- resolved_at
- created_at
- round
- season
- immutable_hash

### remark_reactions
- reaction_id
- remark_id
- user_id
- reaction_type (agree, disagree)
- created_at

### alignment_scores
- score_id
- entity_id (expert, user, or Jaromelu)
- entity_type (expert, user, system)
- score_type (overall, captain_picks, buy_sell, matchup)
- period (round, month, season)
- period_value (e.g. round number or season year)
- total_predictions
- correct_predictions
- alignment_pct
- updated_at

### wiki_pages
- page_id
- entity_id (FK → entities)
- page_type (player, team, advisor, round)
- slug (unique, URL-safe)
- title
- content (markdown with `[[slug]]` wiki-links)
- summary
- metadata_json
- status (stub, draft, published)
- created_at
- updated_at

### wiki_revisions
- revision_id
- page_id (FK → wiki_pages)
- section_heading
- summary (agent-written change description)
- content_snapshot
- source_trigger
- source_id (FK → sources)
- metadata_json
- created_at

### knowledge_base
- kb_id
- kb_type (player_summary, round_brief, decision, opinion, source_digest, article_tips, article_totw, article_trades, article_captains, article_stocks, article_consensus)
- subject_entity_id (optional FK → entities)
- title
- content (markdown)
- embedding (vector 1536, for RAG retrieval)
- metadata_json (structured data — player rankings, consensus counts, etc.)
- effective_round
- season
- source_claim_ids (array of claim UUIDs for attribution)
- created_at
- updated_at
- expires_at (optional)

The `article_*` types power **The Analysis** content hub — see `docs/pages/analysis/overview.md`.

This schema is enough for V1 and does not overcomplicate things.
