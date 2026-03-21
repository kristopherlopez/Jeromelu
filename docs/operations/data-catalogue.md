# Data Catalogue

Personal reference for the JeromeLu data model. Source of truth: `packages/shared/jeromelu_shared/db/models.py`

---

## Data Lineage

```
Channel (registry)
   │
   ▼
Source (YouTube video, podcast, article)
   │
   ▼
SourceDocument (full transcript / text, stored in S3 + raw_text)
   │
   ├──▶ SourceChunk (sliding-window segments, each with embedding)
   │       │
   │       └──▶ ClaimChunk (N:M junction) ──▶ Claim
   │
   ├──▶ Quote (verbatim quote attributed to a speaker Entity)
   │       │
   │       └──▶ Claim (extracted buy/sell/hold assertion about a player Entity)
   │
   ▼
Entity (player, team, expert, matchup)
   │
   ├──▶ ConsensusSnapshot (aggregated sentiment per time bucket)
   ├──▶ Prediction (forecast about an entity, links to evidence claims)
   │       └──▶ Outcome (scored result)
   └──▶ Decision (trade, captain pick, etc.)
           ├──▶ Outcome (scored result)
           └──▶ Event (immutable audit log entry)

PlayerRound ─── standalone scraped stats per player/round/season
PlayerTeamHistory ─── SCD Type 2 player-team assignments
Plan ─── standalone strategy documents per round
```

---

## Entity Relationship Diagram

```
channels ──(1:N)──▶ sources ──(1:N)──▶ source_documents ──(1:N)──▶ source_chunks
                                              │                         │
                                              ├──(1:N)──▶ quotes       │
                                              │              │          │
                                              └──(1:N)──▶ claims ◀──(N:M via claim_chunks)
                                                            │
                                                     entities ◀──────┘
                                                        │
                                          ┌─────────────┼─────────────┐
                                          ▼             ▼             ▼
                                   predictions   consensus_snapshots  decisions
                                       │                                 │
                                       ▼                                 ▼
                                    outcomes ◀───────────────────────  outcomes
                                                                        │
                                                                        ▼
                                                                     events
```

---

## Tables

### channels

Registry of content sources (YouTube channels, podcast feeds, websites).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| channel_id | UUID | PK | uuid4 | |
| slug | text | no | | unique |
| platform | text | no | | `youtube`, `podcast`, `website`, `twitter`, `instagram` |
| external_id | text | yes | | unique with platform |
| name | text | no | | |
| url | text | yes | | |
| description | text | yes | | |
| quality_rating | int | no | 5 | |
| tags | text[] | no | [] | |
| active | bool | no | true | |
| last_polled_at | timestamptz | yes | | |
| created_at | timestamptz | no | now() | |

**Indexes:** platform, active
**Unique:** slug; (platform, external_id)

---

### sources

Individual content items (a specific video, episode, article).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| source_id | UUID | PK | uuid4 | |
| channel_id | UUID | yes | | FK → channels |
| source_type | text | no | | `youtube`, `podcast`, `web`, `radio`, `manual` |
| title | text | no | | |
| creator_name | text | yes | | |
| canonical_url | text | yes | | unique |
| approved_flag | bool | no | false | |
| ingestion_status | text | no | `pending` | |
| published_at | timestamptz | yes | | |
| ingested_at | timestamptz | yes | | |
| created_at | timestamptz | no | now() | |

**Indexes:** source_type, approved_flag
**Unique:** canonical_url
**FK:** channel_id → channels.channel_id

---

### source_documents

Full transcript or text content for a source. One source can have multiple documents.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| document_id | UUID | PK | uuid4 | |
| source_id | UUID | no | | FK → sources |
| s3_key | text | yes | | S3 object key for raw file |
| raw_text | text | yes | | Original transcript text |
| cleaned_text | text | yes | | Post-cleaning text |
| transcript_available | bool | no | false | |
| language | text | no | `en` | |
| checksum | text | yes | | Content hash for dedup |
| chunk_count | int | no | 0 | |
| created_at | timestamptz | no | now() | |

**Indexes:** source_id
**FK:** source_id → sources.source_id

---

### source_chunks

Individual transcript segments (1:1 with deduped auto-caption segments). Each row is a single 5-6 word segment preserving the original YouTube caption boundaries and timestamps.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| chunk_id | UUID | PK | uuid4 | |
| document_id | UUID | no | | FK → source_documents |
| chunk_index | int | no | | Ordering within document |
| raw_text | text | no | | Original auto-caption text |
| clean_text | text | yes | | Post-cleaning text (corrected names, garbled words) |
| start_offset | int | yes | | Character offset in document |
| end_offset | int | yes | | Character offset in document |
| start_ts | float | yes | | Video/audio timestamp (seconds) |
| end_ts | float | yes | | Video/audio timestamp (seconds) |
| embedding | vector(1536) | yes | | pgVector, OpenAI ada-002 dimensions |
| created_at | timestamptz | no | now() | |

**Indexes:** document_id
**FK:** document_id → source_documents.document_id

---

### entities

Named entities: players, teams, experts, matchups. Central reference table.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| entity_id | UUID | PK | uuid4 | |
| entity_type | text | no | | `player`, `team`, `expert`, `matchup` |
| canonical_name | text | no | | |
| aliases | text[] | no | [] | Alternative names/spellings |
| metadata_json | jsonb | no | {} | Flexible metadata |
| created_at | timestamptz | no | now() | |

**Indexes:** entity_type, canonical_name

---

### quotes

Direct quotes extracted from source documents, attributed to a speaker.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| quote_id | UUID | PK | uuid4 | |
| document_id | UUID | no | | FK → source_documents |
| chunk_id | UUID | yes | | FK → source_chunks |
| speaker_entity_id | UUID | yes | | FK → entities |
| quoted_text | text | no | | |
| start_offset | int | yes | | Character offset |
| end_offset | int | yes | | Character offset |
| said_at_reference | text | yes | | Temporal reference in source |
| confidence | float | yes | | Extraction confidence 0-1 |
| created_at | timestamptz | no | now() | |

**Indexes:** document_id, speaker_entity_id
**FK:** document_id → source_documents; chunk_id → source_chunks; speaker_entity_id → entities

---

### claims

Extracted assertions about players/entities (buy, sell, hold, etc.).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| claim_id | UUID | PK | uuid4 | |
| document_id | UUID | yes | | FK → source_documents |
| quote_id | UUID | yes | | FK → quotes |
| subject_entity_id | UUID | yes | | FK → entities (who the claim is about) |
| claim_type | text | no | | `buy`, `sell`, `hold`, `captain`, `avoid`, `breakout`, `matchup_edge` |
| claim_text | text | yes | | Human-readable claim summary |
| polarity | float | yes | | Positive/negative sentiment |
| strength | float | yes | | Conviction level |
| effective_round | int | yes | | NRL round this applies to |
| season | int | yes | | NRL season year |
| start_ts | float | yes | | Video timestamp start (seconds) |
| end_ts | float | yes | | Video timestamp end (seconds) |
| extracted_at | timestamptz | no | now() | |

**Indexes:** subject_entity_id, claim_type, document_id, (effective_round, season)
**FK:** document_id → source_documents; quote_id → quotes; subject_entity_id → entities

---

### claim_chunks

Junction table linking claims to the source chunks they were extracted from (N:M).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| claim_id | UUID | PK | | FK → claims (CASCADE delete) |
| chunk_id | UUID | PK | | FK → source_chunks (CASCADE delete) |
| ordinal | int | no | 0 | Ordering of chunks for this claim |

**Indexes:** chunk_id
**Composite PK:** (claim_id, chunk_id)

---

### predictions

Forecasts about future events, linked to evidence claims.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| prediction_id | UUID | PK | uuid4 | |
| predictor_entity_id | UUID | yes | | FK → entities (who made the prediction) |
| subject_entity_id | UUID | yes | | FK → entities (who it's about) |
| prediction_type | text | yes | | |
| predicted_value_text | text | yes | | |
| event_window | text | yes | | e.g. "Round 5", "2026 season" |
| evidence_claim_ids | UUID[] | no | [] | Array of claim_ids backing this |
| created_at | timestamptz | no | now() | |
| resolved_at | timestamptz | yes | | When outcome was determined |
| resolution_status | text | yes | | |

**Indexes:** predictor_entity_id, subject_entity_id
**FK:** predictor_entity_id → entities; subject_entity_id → entities

---

### consensus_snapshots

Aggregated claim sentiment for an entity at a point in time.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| snapshot_id | UUID | PK | uuid4 | |
| subject_entity_id | UUID | no | | FK → entities |
| time_bucket | timestamptz | no | | Aggregation window |
| buy_count | int | no | 0 | |
| sell_count | int | no | 0 | |
| hold_count | int | no | 0 | |
| neutral_count | int | no | 0 | |
| contrarian_score | float | yes | | |
| consensus_score | float | yes | | |
| created_at | timestamptz | no | now() | |

**Indexes:** (subject_entity_id, time_bucket)
**FK:** subject_entity_id → entities

---

### decisions

Action decisions made in the system (trades, captain picks, etc.).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| decision_id | UUID | PK | uuid4 | |
| decision_type | text | no | | `trade`, `captain`, `start_sit`, `squad_structure`, `article_topic`, `reply` |
| subject_entity_id | UUID | yes | | FK → entities |
| action_json | jsonb | no | {} | Structured action payload |
| rationale_summary | text | yes | | |
| strategy_tag | text | yes | | |
| created_at | timestamptz | no | now() | |
| executed_at | timestamptz | yes | | |
| public_flag | bool | no | false | |

**Indexes:** decision_type
**FK:** subject_entity_id → entities

---

### plans

Strategy documents per round.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| plan_id | UUID | PK | uuid4 | |
| status | text | no | `draft` | |
| round_number | int | yes | | |
| plan_summary | text | yes | | |
| scenario_json | jsonb | no | {} | |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | Auto-updates on change |

---

### events

Immutable audit trail of system activity. Entries are hashed for tamper detection.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| event_id | UUID | PK | uuid4 | |
| event_type | text | no | | |
| related_entity_ids | UUID[] | no | [] | |
| related_decision_id | UUID | yes | | FK → decisions |
| related_prediction_id | UUID | yes | | FK → predictions |
| display_text | text | no | | |
| display_mode | text | no | | `thought`, `action`, `system`, `prediction`, `review` |
| visibility | text | no | `public` | `public`, `private` |
| created_at | timestamptz | no | now() | |
| immutable_hash | text | yes | | SHA256 of event payload |

**Indexes:** event_type, created_at, visibility
**FK:** related_decision_id → decisions; related_prediction_id → predictions

---

### outcomes

Scored results for predictions and decisions after events occur.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| outcome_id | UUID | PK | uuid4 | |
| prediction_id | UUID | yes | | FK → predictions |
| decision_id | UUID | yes | | FK → decisions |
| actual_value_json | jsonb | yes | | |
| result_label | text | yes | | |
| scored_at | timestamptz | no | now() | |

**FK:** prediction_id → predictions; decision_id → decisions

---

### player_rounds

Per-player performance stats for each round/season. Scraped from external sources, no FK relationships.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| player_id | int | no | | External player ID |
| player_name | text | no | | |
| team | text | no | | |
| position | text | no | | |
| round | int | no | | |
| season | int | no | | |
| **Core** | | | | |
| score | int | yes | | SC total score |
| price | int | yes | | Current price |
| breakeven | int | yes | | BE score |
| minutes | int | yes | | Minutes played |
| selected_pct | float | yes | | Ownership % |
| **SC Breakdown** | | | | |
| base | int | yes | | Base SC points |
| attack | int | yes | | Attack SC points |
| playmaking | int | yes | | Playmaking SC points |
| power | int | yes | | Power SC points |
| negative | int | yes | | Negative SC points |
| **Scoring** | | | | |
| tries | int | yes | | |
| try_assists | int | yes | | |
| goals | int | yes | | |
| missed_goals | int | yes | | |
| field_goals | int | yes | | |
| missed_field_goals | int | yes | | |
| **Attack** | | | | |
| line_breaks | int | yes | | |
| line_break_assists | int | yes | | |
| last_touch | int | yes | | |
| tackle_busts | int | yes | | |
| offloads | int | yes | | |
| ineffective_offloads | int | yes | | |
| hitups_8m | int | yes | | Hitups gaining 8+ metres |
| hitups_under_8m | int | yes | | Hitups gaining <8 metres |
| kick_metres | int | yes | | |
| **Defence** | | | | |
| tackles_made | int | yes | | |
| missed_tackles | int | yes | | |
| intercepts | int | yes | | |
| **Discipline** | | | | |
| forced_dropouts | int | yes | | |
| forty_twentys | int | yes | | |
| kicked_dead | int | yes | | |
| penalties | int | yes | | |
| errors | int | yes | | |
| sin_bins | int | yes | | |
| handover_given | int | yes | | |
| **Derived** | | | | |
| ppm | float | yes | | Points per minute |
| base_ppm | float | yes | | Base points per minute |
| base_power | int | yes | | base + power |
| base_power_ppm | float | yes | | (base + power) / minutes |
| **Averages** | | | | |
| avg_score | float | yes | | Season average |
| two_rd_avg | float | yes | | Last 2 rounds |
| three_rd_avg | float | yes | | Last 3 rounds |
| five_rd_avg | float | yes | | Last 5 rounds |
| season_avg | float | yes | | Full season average |
| **Percentages** | | | | |
| hitup_8m_pct | float | yes | | hitups_8m / total hitups |
| tackle_bust_pct | float | yes | | |
| missed_tackle_pct | float | yes | | |
| offload_involvement_pct | float | yes | | |
| base_pct | float | yes | | base / score |
| **Price** | | | | |
| start_price | int | yes | | Price at round start |
| end_price | int | yes | | Price at round end |
| round_price_change | int | yes | | |
| season_price_change | int | yes | | |
| magic_number | int | yes | | Score needed to increase in price |
| **Context** | | | | |
| opposition | text | yes | | |
| venue | text | yes | | |
| weather | text | yes | | |
| surface | text | yes | | |
| jersey | int | yes | | Jersey number |
| bye_round | text | yes | | |
| created_at | timestamptz | no | now() | |

**Unique:** (player_id, round, season)
**Indexes:** (season, round), player_id

---

### player_team_history

SCD Type 2 table tracking which team a player belongs to over time.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| player_name | text | no | | |
| team_key | text | no | | Short team identifier |
| team_name | text | no | | Full team name |
| position | text | yes | | |
| player_id | int | yes | | External player ID |
| effective_from | date | no | | Start of assignment |
| effective_to | date | yes | | End of assignment (null = current) |
| is_current | bool | no | true | |
| source | text | no | `seed` | How the record was created |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | Auto-updates on change |

**Unique:** (player_name, effective_from)
**Indexes:** (player_name, is_current), (team_key, is_current), player_id

---

## Enums

| Enum | Values |
|------|--------|
| channel.platform | `youtube`, `podcast`, `website`, `twitter`, `instagram` |
| source.source_type | `youtube`, `podcast`, `web`, `radio`, `manual` |
| entity.entity_type | `player`, `team`, `expert`, `matchup` |
| claim.claim_type | `buy`, `sell`, `hold`, `captain`, `avoid`, `breakout`, `matchup_edge` |
| decision.decision_type | `trade`, `captain`, `start_sit`, `squad_structure`, `article_topic`, `reply` |
| event.display_mode | `thought`, `action`, `system`, `prediction`, `review` |
| event.visibility | `public`, `private` |

---

## Migrations

| # | File | What it does |
|---|------|-------------|
| 001 | `001_initial_schema.sql` | Core tables: sources, source_documents, source_chunks, entities, quotes, claims, predictions, consensus_snapshots, decisions, events, plans, outcomes |
| 002 | `002_add_channels.sql` | Add channels table |
| 003 | `003_add_channel_fk_to_sources.sql` | Add channel_id FK to sources |
| 004 | `004_add_player_rounds.sql` | Add player_rounds table |
| 005 | `005_add_player_team_history.sql` | Add player_team_history SCD2 table |
| 006 | `006_claims_rework.sql` | Add claim_chunks junction table, add season to claims |
| 007 | `007_enrich_player_rounds.sql` | Add derived stats, averages, percentages, price tracking, context columns to player_rounds |
| 008 | `008_add_claim_timestamps.sql` | Add start_ts/end_ts to claims |
| 009 | `009_chunk_raw_clean_text.sql` | Rename text → raw_text, add clean_text to source_chunks |
