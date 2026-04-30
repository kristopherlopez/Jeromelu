# Data Catalogue

Personal reference for the Jaromelu data model. Source of truth: `packages/shared/jeromelu_shared/db/models.py`

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
Entity (player, team, expert/advisor, matchup, round)
   │
   ├──▶ ConsensusSnapshot (aggregated sentiment per time bucket)
   ├──▶ Prediction (forecast about an entity, links to evidence claims)
   │       └──▶ Outcome (scored result)
   ├──▶ Decision (trade, captain pick, etc.)
   │       ├──▶ Outcome (scored result)
   │       └──▶ Event (immutable audit log entry)
   ├──▶ Remark (voiced, opinionated public position with open→locked→resolved lifecycle)
   │       └──▶ RemarkReaction (audience agree/disagree)
   ├──▶ AlignmentScore (per-entity prediction accuracy over time)
   └──▶ WikiPage (prose, agent-maintained page)
           └──▶ WikiRevision (edit log per section)

Derived / downstream:
KnowledgeBase (distilled entries embedded for RAG; includes analysis articles)
PlayerRound ─── standalone scraped stats per player/round/season
PlayerAttributes ─── SCD-2 of slow-changing player facts (team, position, height/weight, contract)
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

### teams

Canonical roster of every team across all grades feeding into NRL — NRL,
NRLW, NSW Cup, QLD Cup (Hostplus Cup), and the junior pathway grades
(Jersey Flegg, Mal Meninga, SG Ball, Cyril Connell, Harold Matthews —
schema-allowed; not yet seeded). `parent_team_id` self-references to link
a feeder team to its senior NRL/NRLW side; `entity_id` links senior rows
to the canonical `entities` row so claims/predictions/wiki pages tie back
without duplication. Feeder grades typically inherit identity via
`parent_team_id` and leave `entity_id` NULL.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| team_id | UUID | PK | uuid4 | |
| slug | text | no | | UNIQUE; e.g. `brisbane_broncos`, `norths_devils`, `brisbane_broncos_nrlw` |
| name | text | no | | Full team name |
| short_name | text | yes | | e.g. `Broncos` |
| aliases | text[] | no | `{}` | Lower-grade rows may be empty |
| grade | text | no | | `nrl`, `nrlw`, `nsw_cup`, `qld_cup`, `jersey_flegg`, `mal_meninga`, `sg_ball`, `cyril_connell`, `harold_matthews` |
| competition | text | yes | | e.g. `NRL Premiership`, `NSW Cup` |
| parent_team_id | UUID | yes | | FK → teams (senior team this feeds into; NULL for top grades) |
| entity_id | UUID | yes | | UNIQUE; FK → entities; populated for NRL/NRLW rows |
| metadata_json | jsonb | no | {} | |
| active | bool | no | true | |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | Auto-updates |

**Unique:** slug, entity_id
**Indexes:** grade, parent_team_id, entity_id, active
**FK:** parent_team_id → teams (ON DELETE SET NULL); entity_id → entities (ON DELETE SET NULL)

Seeded from `data/teams.yaml` via `make seed-teams` (script: `scripts/data/seed_teams.py`). Idempotent.

---

### player_attributes

SCD Type 2 of slow-changing player facts. Replaces `player_team_history`
(dropped in migration 027). Holds team affiliation, primary position,
height/weight and contract info on one row per current state — closed and
reopened on change. Lifetime constants (dob, debut date) live on
`entities.metadata_json`; per-round facts (price, breakeven, score, jersey,
grade) live on `player_rounds`.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| entity_id | UUID | no | | FK → entities (ON DELETE CASCADE) |
| team_id | UUID | yes | | FK → teams (ON DELETE SET NULL); parent NRL/NRLW row even when player is on a feeder grade |
| primary_position | text | yes | | SC position string (FRF, HOK, HFB, ...) |
| height_cm | int | yes | | |
| weight_kg | int | yes | | |
| contract_until | date | yes | | Real-world contract end |
| real_salary_aud | int | yes | | Reserved for future feed; NULL today |
| metadata_json | jsonb | no | `{}` | secondary_positions, captain, status='retired', supercoach_id mirror |
| effective_from | date | no | | Start of this state |
| effective_to | date | yes | | End of state (NULL = current) |
| is_current | bool | no | true | |
| source | text | no | `seed` | `supercoach`, `nrl_com`, `nswrl_com`, `qrl_com`, `seed`, ... |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | |

**Indexes:** (entity_id, is_current), (team_id, is_current)
**Unique partial index:** entity_id WHERE is_current — exactly one current row per entity
**Check:** `effective_to IS NULL OR effective_to >= effective_from`

Populated via the player-roster admin endpoints — see [player roster](../agents/system/player-roster.md). Local dev seed: `make seed-players` (after `make seed-teams`).

---

### knowledge_base

Distilled, structured knowledge chunks embedded for RAG retrieval. Also stores Analysis articles.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| kb_id | UUID | PK | uuid4 | |
| kb_type | text | no | | `player_summary`, `round_brief`, `decision`, `opinion`, `source_digest`, `article_tips`, `article_totw`, `article_trades`, `article_captains`, `article_stocks`, `article_consensus` |
| subject_entity_id | UUID | yes | | FK → entities (optional) |
| title | text | yes | | |
| content | text | no | | Markdown body |
| embedding | vector(1536) | yes | | For RAG retrieval |
| metadata_json | jsonb | no | {} | Player rankings, consensus counts, etc. |
| effective_round | int | yes | | |
| season | int | yes | | |
| source_claim_ids | UUID[] | no | [] | Attribution — claim UUIDs used |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | |
| expires_at | timestamptz | yes | | Optional TTL |

**Indexes:** kb_type, (effective_round, season), subject_entity_id, embedding (HNSW / IVFFlat)
**FK:** subject_entity_id → entities

Powers [Ask Me](../pages/ask-me/overview.md) (RAG) and [The Analysis](../pages/analysis/overview.md) (`article_*` types).

---

### wiki_pages

Prose per-entity knowledge pages, written and maintained by a managed agent.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| page_id | UUID | PK | uuid4 | |
| entity_id | UUID | no | | FK → entities (one page per entity) |
| page_type | text | no | | `player`, `team`, `advisor`, `round` |
| slug | text | no | | URL slug, unique |
| title | text | no | | Display name |
| content | text | no | | Markdown with `[[slug]]` wiki-links |
| summary | text | yes | | One-liner for listings |
| metadata_json | jsonb | no | {} | Tags, sidebar data |
| status | text | no | `stub` | `stub`, `draft`, `published` |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | Auto-updates |

**Unique:** slug
**FK:** entity_id → entities

Powers [The Wiki](../pages/wiki/overview.md).

---

### wiki_revisions

Per-section edit log for wiki pages.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| revision_id | UUID | PK | uuid4 | |
| page_id | UUID | no | | FK → wiki_pages (CASCADE) |
| section_heading | text | yes | | Null = full page |
| summary | text | no | | Agent-written change description |
| content_snapshot | text | yes | | Optional snapshot of the section |
| source_trigger | text | yes | | e.g. `managed-agent/claims-upload` |
| source_id | UUID | yes | | FK → sources (optional) |
| metadata_json | jsonb | no | {} | |
| created_at | timestamptz | no | now() | |

**Indexes:** page_id, created_at
**FK:** page_id → wiki_pages (CASCADE); source_id → sources

Powers the wiki activity feed (`GET /api/wiki/recent-changes`).

---

### remarks

The atomic output unit: an opinionated, voiced analytical piece with an open → locked → resolved lifecycle.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| remark_id | UUID | PK | uuid4 | |
| voice_text | text | no | | Jaromelu's voiced output |
| subject_entity_ids | UUID[] | no | [] | Players/teams/matchups referenced |
| position | text | yes | | `buy`, `sell`, `hold`, `captain`, `avoid` |
| conviction | text | yes | | `low`, `medium`, `high` |
| status | text | no | `open` | `open`, `locked`, `resolved` |
| evidence_claim_ids | UUID[] | no | [] | Upstream claims backing this |
| decision_id | UUID | yes | | FK → decisions |
| resolution_json | jsonb | yes | | Outcome data once resolved |
| resolved_at | timestamptz | yes | | |
| round | int | yes | | |
| season | int | yes | | |
| created_at | timestamptz | no | now() | |
| immutable_hash | text | yes | | SHA256 of remark payload |

**Indexes:** status, (round, season)
**FK:** decision_id → decisions

---

### remark_reactions

Audience reactions to open/locked Remarks.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| reaction_id | UUID | PK | uuid4 | |
| remark_id | UUID | no | | FK → remarks |
| user_id | UUID | yes | | |
| reaction_type | text | no | | `agree`, `disagree` |
| created_at | timestamptz | no | now() | |

**FK:** remark_id → remarks

---

### alignment_scores

Prediction accuracy tracking per entity (expert, user, or system). Powers [The Ledger](../pages/ledger/overview.md)'s Alignment Index.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| score_id | UUID | PK | uuid4 | |
| entity_id | UUID | no | | FK → entities |
| entity_type | text | no | | `expert`, `user`, `system` |
| score_type | text | no | | `overall`, `captain_picks`, `buy_sell`, `matchup` |
| period | text | no | | `round`, `month`, `season` |
| period_value | text | yes | | e.g. round number or season year |
| total_predictions | int | no | 0 | |
| correct_predictions | int | no | 0 | |
| alignment_pct | float | yes | | |
| updated_at | timestamptz | no | now() | |

**Indexes:** (entity_id, score_type, period, period_value)
**FK:** entity_id → entities

---

### squad_slots, squad_trades (deprecated)

Originally designed for the retired "My Squad" page. Tables remain in the schema but are not actively written or read by the live app. See [architecture/04-information-architecture.md](../architecture/04-information-architecture.md).

---

## Enums

| Enum | Values |
|------|--------|
| channel.platform | `youtube`, `podcast`, `website`, `twitter`, `instagram` |
| source.source_type | `youtube`, `podcast`, `web`, `radio`, `manual` |
| entity.entity_type | `player`, `team`, `expert`, `advisor`, `matchup`, `round` |
| teams.grade | `nrl`, `nrlw`, `nsw_cup`, `qld_cup`, `jersey_flegg`, `mal_meninga`, `sg_ball`, `cyril_connell`, `harold_matthews` |
| claim.claim_type | `buy`, `sell`, `hold`, `captain`, `avoid`, `breakout`, `matchup_edge` |
| decision.decision_type | `trade`, `captain`, `start_sit`, `squad_structure`, `article_topic`, `reply` |
| event.display_mode | `thought`, `action`, `system`, `prediction`, `review`, `wiki_update` |
| event.visibility | `public`, `private` |
| remark.status | `open`, `locked`, `resolved` |
| remark.position | `buy`, `sell`, `hold`, `captain`, `avoid` |
| remark.conviction | `low`, `medium`, `high` |
| remark_reaction.reaction_type | `agree`, `disagree` |
| wiki_page.page_type | `player`, `team`, `advisor`, `round` |
| wiki_page.status | `stub`, `draft`, `published` |
| kb.kb_type | `player_summary`, `round_brief`, `decision`, `opinion`, `source_digest`, `article_tips`, `article_totw`, `article_trades`, `article_captains`, `article_stocks`, `article_consensus` |
| alignment_scores.entity_type | `expert`, `user`, `system` |
| alignment_scores.score_type | `overall`, `captain_picks`, `buy_sell`, `matchup` |
| alignment_scores.period | `round`, `month`, `season` |

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
| 010+ | (verify actual migration filenames) | knowledge_base table, remarks + remark_reactions, alignment_scores, squad_slots + squad_trades (now deprecated) |
| 015 | `015_wiki.sql` | wiki_pages + wiki_revisions tables |
| 026 | `026_teams.sql` | teams table — canonical roster across all NRL pathway grades + NRLW |
| 027 | `027_consolidate_player_scd.sql` | Add player_attributes (SCD-2) with team_id FK to teams; drop player_team_history |

> The migrations list above drifts — verify against `packages/db/migrations/` for authoritative state. Whenever a new migration lands, update this table + the relevant table section + the lineage diagram.
