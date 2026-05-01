---
tags: [area/operations]
---

# Data Catalogue

Personal reference for the Jaromelu data model. Source of truth: `packages/shared/jeromelu_shared/db/models.py`

The schema breaks into five layers:

- **Identity** — `entities` is the noun layer. Anything referenced, claimed about, predicted on, or wiki-able lives here.
- **Structured world** — Real things and their facts: teams, venues, fixtures, rosters, injuries, per-round stats. Each row may link back to identity via `entity_id`.
- **Content & claims** — Pipeline from channel → source → document → overlays → quote → claim, plus time-series popularity sidecars.
- **Reasoning & output** — What Jaromelu produces from the world plus the content: predictions, decisions, remarks, alignment scores, knowledge base, wiki.
- **Agent audit** — Per-run and per-event observability for Claude-Agent-SDK-based agents.

---

## Schema Overview

```
Layer 1 — IDENTITY ─────────────────────────────────────────────────────────────
                          ┌───────────────────────────────────┐
                          │             entities              │   ◄─── referenced from every layer
                          │  (player | team | advisor |       │
                          │   coach | referee | commentator | │
                          │   journalist | match | round |    │
                          │   venue)                          │
                          └───────────────────────────────────┘
                                          ▲
Layer 2 — STRUCTURED WORLD ───────────────┼─────────────────────────────────────
                                          │ entity_id (teams, venues, matches)
       ┌────────┐  ┌────────┐  ┌─────────┐  ┌──────────────────┐  ┌──────────┐
       │ teams  │  │ venues │  │ matches │──│ match_team_lists │  │ injuries │
       └────────┘  └────────┘  └─────────┘  └──────────────────┘  └──────────┘
                                    ▲                ▲
                                    │                │
                            ┌────────────────────┐    ┌─────────────────────┐
                            │   player_rounds    │    │  player_attributes  │
                            │  (SC overlay,      │    │       (SCD-2)       │
                            │  FK→match,team)    │    └─────────────────────┘
                            └────────────────────┘

Layer 3 — CONTENT & CLAIMS ─────────────────────────────────────────────────────
   scout_candidates ──(promote)──▶ channels / sources    (Scout's review queue)
   channels ──▶ sources ──▶ source_documents
      │           │              ├──▶ source_chunks       (atomic caption-level segments)
      │           │              ├──▶ source_speakers     (diarised turns)
      │           │              ├──▶ source_chapters     (semantic chapters)
      │           │              ├──▶ source_annotations  (generic overlays)
      │           │              ├──▶ quotes  ─────────┐
      │           │              └──▶ claims  ◄────────┘
      │           │                     │
      │           │                     └──▶ claim_chunks  (N:M with source_chunks)
      ▼           ▼
   channel_metrics   video_metrics       (time-series popularity sidecars)

Layer 4 — REASONING & OUTPUT ───────────────────────────────────────────────────
   predictions ──▶ outcomes               decisions ──▶ outcomes ──▶ events
   consensus_snapshots                    plans
   remarks ──▶ remark_reactions           alignment_scores
   knowledge_base                         wiki_pages ──▶ wiki_revisions
   squad_slots  (planned)                 squad_trades  (planned)

Layer 5 — AGENT AUDIT ──────────────────────────────────────────────────────────
   agent_runs ──(run_id)──▶ agent_events    (per-run summary + per-event trail)
```

---

## 1. Identity (entities)

The "noun" layer. Every other table references entities for anything Jaromelu claims about, predicts on, or wikis.

### entities

Central reference table for every "noun" Jaromelu can claim about, predict on, or wiki.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| entity_id | UUID | PK | uuid4 | |
| entity_type | text | no | | `player`, `team`, `advisor`, `coach`, `referee`, `commentator`, `journalist`, `match`, `round`, `venue`. Denormalised — equals the role of the entity's primary current `entity_roles` row. |
| canonical_name | text | no | | |
| aliases | text[] | no | [] | Alternative names/spellings |
| slug | text | yes | | URL-safe slug |
| metadata_json | jsonb | no | {} | Lifetime constants (player dob/debut, team colours, venue location, etc.) |
| created_at | timestamptz | no | now() | |

**Indexes:** entity_type, canonical_name

---

### entity_roles

SCD-2 of role tenure per entity. Lets a single entity carry multiple roles over time without duplicating identity — e.g. Andrew Johns (player → commentator), Michael Ennis (player → coach + commentator), Adam Reynolds (active player + occasional commentator).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| entity_role_id | UUID | PK | uuid4 | |
| entity_id | UUID | no | | FK → entities (CASCADE) |
| role | text | no | | `player`, `coach`, `commentator`, `journalist`, `referee`, `advisor` |
| effective_from | date | no | | Start of tenure |
| effective_to | date | yes | | End of tenure (NULL = current) |
| is_primary | bool | no | false | Exactly one primary current row per entity |
| metadata_json | jsonb | no | {} | |
| source | text | no | `seed` | `seed`, `backfill_018`, `manual`, ... |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | |

**Indexes:** (entity_id, effective_to), (role, effective_from, effective_to)
**Unique partial index:** entity_id WHERE is_primary AND effective_to IS NULL — exactly one primary current role per entity
**Check:** `effective_to IS NULL OR effective_to >= effective_from`
**FK:** entity_id → entities (CASCADE)

`entities.entity_type` denormalises from this table — it always equals the role of the primary current row (the partial unique index makes that well-defined). Non-people types (`team`, `match`, `round`, `venue`) typically have no `entity_roles` rows.

---

## 2. Structured world

Real-world rows holding facts. Most can link to `entities` via `entity_id` when that thing has identity worth claiming about.

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

### venues

Stadium reference table. Slow-changing — roughly 25–30 NRL/NRLW grounds plus
the occasional one-off (Magic Round host city, country trial venues).
Referenced by `matches.venue_id`.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| venue_id | UUID | PK | uuid4 | |
| slug | text | no | | UNIQUE; e.g. `suncorp_stadium`, `accor_stadium` |
| name | text | no | | Current sponsored name |
| aliases | text[] | no | `{}` | Sponsorship history + colloquial names; used for fuzzy match on ingest |
| city | text | yes | | |
| state | text | yes | | NULL for non-AU venues |
| country | text | no | `AU` | ISO-style country code (`AU`, `NZ`) |
| capacity | int | yes | | |
| surface | text | yes | | `grass`, `hybrid`, `synthetic` |
| roof | text | yes | | `open`, `closed`, `retractable` |
| tz | text | yes | | IANA timezone (`Australia/Brisbane`, `Australia/Sydney`, `Pacific/Auckland`); QLD venues do NOT observe DST |
| entity_id | UUID | yes | | UNIQUE; FK → entities; populated when the venue is discussed (e.g. "Suncorp under lights") |
| metadata_json | jsonb | no | {} | |
| active | bool | no | true | |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | Auto-updates |

**Unique:** slug; entity_id
**Indexes:** active, (country, state)

Seeded from `data/venues.yaml` via `make seed-venues` (script: `scripts/data/seed_venues.py`). Idempotent.

---

### matches

Fixture / result spine — one row per game across all grades (NRL, NRLW,
NSW Cup, QLD Cup, junior pathway). Real-world side of the model;
`player_rounds` is the SuperCoach overlay that joins via `match_id`.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| match_id | UUID | PK | uuid4 | |
| source | text | no | `nrl_com` | Upstream feed identifier — `nrl_com`, `supercoach`, `manual` |
| external_match_id | text | yes | | Upstream id; combined with `source` for idempotent upsert |
| season | int | no | | |
| round | int | yes | | NULL for finals — use `round_label` |
| round_label | text | yes | | Human form ("Finals Week 1", "Magic Round") |
| grade | text | no | | Mirrors `teams.grade` |
| home_team_id | UUID | no | | FK → teams (RESTRICT) |
| away_team_id | UUID | no | | FK → teams (RESTRICT) |
| venue_id | UUID | yes | | FK → venues (SET NULL) |
| kickoff_at | timestamptz | yes | | UTC; render in `venues.tz` |
| status | text | no | `scheduled` | `scheduled`, `live`, `final`, `postponed`, `cancelled`, `forfeit` |
| home_score | int | yes | | Paired — both NULL or both set |
| away_score | int | yes | | |
| weather | text | yes | | |
| referee_name | text | yes | | |
| broadcast | text | yes | | |
| entity_id | UUID | yes | | UNIQUE; FK → entities; replaces the old `matchup` entity_type so claims/predictions can target a specific game |
| metadata_json | jsonb | no | {} | Ladder context, byes, rep weekend flags |
| last_synced_at | timestamptz | yes | | When the fixture-sync last touched this row |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | Auto-updates |

**Unique:** (source, season, grade, external_match_id) — partial, only when external_match_id is set; entity_id
**Indexes:** (season, round, grade), kickoff_at, status, home_team_id, away_team_id, venue_id
**Constraints:** home_team_id ≠ away_team_id; scores paired
**FK:** home_team_id, away_team_id → teams.team_id (RESTRICT); venue_id → venues.venue_id (SET NULL)

Populated by the daily fixture-sync against the NRL.com draw API (see `docs/agents/system/scraper.md`).

---

### match_team_lists

Versioned named-17 announcements per match per team. Each new public lineup
(Tuesday list, Thursday list, late changes) appends a row with an
incremented `list_version` rather than mutating the prior row.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| list_id | UUID | PK | uuid4 | |
| match_id | UUID | no | | FK → matches (CASCADE) |
| team_id | UUID | no | | FK → teams (RESTRICT) |
| player_entity_id | UUID | no | | FK → entities (RESTRICT); player |
| jersey_number | int | yes | | 1..30 (allows reserves) |
| named_position | text | yes | | `fullback`, `wing`, `centre`, `five-eighth`, `halfback`, `hooker`, `prop`, `second-row`, `lock`, `interchange`, `reserve` |
| sc_position | text | yes | | SC position string (HOK/HFB/CTW/FRF/2RF/MID/FLB/FLX) — populated when the SC API is the source |
| list_version | int | no | 1 | Monotonically increasing per (match, team) |
| status | text | no | `named` | `named`, `late_change_in`, `late_change_out`, `19th_man`, `reserve`, `withdrawn` |
| announced_at | timestamptz | yes | | |
| source | text | no | `nrl_com` | |
| metadata_json | jsonb | no | {} | |
| created_at | timestamptz | no | now() | |

**Unique:** (match_id, team_id, player_entity_id, list_version)
**Indexes:** match_id, team_id, player_entity_id, (match_id, team_id, list_version DESC)
**FK:** match_id → matches (CASCADE); team_id → teams (RESTRICT); player_entity_id → entities (RESTRICT)

Live current state for a fixture: filter by (match_id, team_id) and pick `list_version` DESC.

---

### injuries

Append-on-change timeline of player injury / suspension state. Each daily
casualty-ward sweep writes a new row only when a player's status has
actually changed (or appeared for the first time).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| injury_id | UUID | PK | uuid4 | |
| player_entity_id | UUID | no | | FK → entities (CASCADE) |
| team_id | UUID | yes | | FK → teams (SET NULL) |
| status | text | no | | `training`, `test`, `1_week`, `2_4_weeks`, `4_8_weeks`, `indefinite`, `season`, `suspended`, `cleared` |
| body_part | text | yes | | `hamstring`, `knee_acl`, `head`, `ankle`, ... |
| mechanism | text | yes | | `collision`, `non_contact`, `illness`, `concussion_protocol`, `suspension`, `unknown` |
| description | text | yes | | Raw text from the source |
| expected_return_round | int | yes | | |
| expected_return_date | date | yes | | |
| severity | text | yes | | `low`, `moderate`, `high`, `season` |
| reported_at | timestamptz | no | | When the source published the change |
| resolved_at | timestamptz | yes | | Set on the prior open row when status flips to `cleared` |
| source | text | no | | `nrl_com_casualty`, `zerotackle`, `nrl_physio_twitter`, `manual` |
| source_url | text | yes | | |
| metadata_json | jsonb | no | {} | |
| created_at | timestamptz | no | now() | |

**Indexes:** (player_entity_id, reported_at DESC), (team_id, status) WHERE resolved_at IS NULL, reported_at
**FK:** player_entity_id → entities (CASCADE); team_id → teams (SET NULL)

"Latest known status for player X": ORDER BY reported_at DESC LIMIT 1.

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

### player_rounds

Per-player SuperCoach performance overlay — one row per player per round per season. Joins to the fixture spine via `match_id` (FK→matches) and `team_id` (FK→teams). External `player_id` keys back to the SC API.

The table has ~60 columns covering core stats, SC breakdown (base / attack / playmaking / power / negative), per-event scoring, derived metrics (PPM, base+power), 2/3/5-round averages, percentage breakdowns, and price tracking. **See [Appendix A](#appendix-a-player_rounds-full-column-list) for the complete column list.**

Identity / FK columns (the rest are in the appendix):

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| player_id | int | no | | External SC player ID |
| player_name | text | no | | |
| team | text | no | | Legacy free-text — pre-mig 032 rows |
| position | text | no | | |
| round | int | no | | |
| season | int | no | | |
| opposition | text | yes | | Legacy free-text — pre-mig 032 rows |
| venue | text | yes | | Legacy free-text — pre-mig 032 rows |
| match_id | UUID | yes | | FK → matches; new writes only (mig 032) |
| team_id | UUID | yes | | FK → teams; new writes only (mig 032) |
| created_at | timestamptz | no | now() | |
| *(scoring / derived / averages / price)* | | | | See Appendix A |

**Unique:** (player_id, round, season)
**Indexes:** (season, round), player_id, match_id (partial), team_id (partial)
**FK:** match_id → matches.match_id (ON DELETE SET NULL); team_id → teams.team_id (ON DELETE SET NULL)

The legacy `team`/`opposition`/`venue` text columns stay populated so historical queries keep working; new writes (after migration 032) populate `match_id` and `team_id` alongside the text columns.

---

## 3. Content & claims

Pipeline from channel → source → document → overlays → quote → claim. Overlays sit at the document level (spans defined by `start_ts`/`end_ts`) with chunks remaining the atomic caption-level unit; chunks fall within a speaker turn or chapter by timestamp containment.

Upstream of `channels` and `sources` is `scout_candidates` — Scout's review queue, where unapproved candidates wait before promotion into the canonical tables.

### scout_candidates

Scout's candidate inbox. Scout (the source-discovery agent) writes here as it hunts the web for new NRL channels and videos worth onboarding. Humans approve / reject via the admin review queue; approval promotes a row into the canonical `channels` (kind=channel) or `sources` (kind=video) tables.

Distinct from `sources` so unapproved noise does not pollute the main pipeline. Renamed from `discovered_sources` in migration 035.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| kind | text | no | | `channel`, `video` |
| platform | text | no | `youtube` | Mirrors `channels.platform` |
| external_id | text | no | | YouTube channel_id or video_id |
| url | text | no | | |
| title | text | no | | |
| description | text | yes | | |
| channel_external_id | text | yes | | For videos: parent channel's external id |
| content_categories | text[] | no | {} | `match`, `analysis`, `news`, `injury`, `tactical`, `opinion`, `player-content`, `classic`, `rules-officiating`, `supercoach`, `nrlw`, `origin`, `international`, `junior` |
| score | numeric | yes | | Scout's qualitative score 0..1 |
| score_reasons | jsonb | no | [] | Free-text reasons (e.g. "Australian focus", "10k+ subs") |
| metadata_json | jsonb | no | {} | Discovery-time enrichment (subs, view_count, published_at, etc.) |
| discovered_via | text | no | | Query string OR `related-to:<channel_id>` OR `manual` |
| discovered_at | timestamptz | no | now() | |
| status | text | no | `pending` | `pending`, `approved`, `rejected`, `snoozed`, `duplicate` |
| reviewed_at | timestamptz | yes | | |
| reviewed_by | text | yes | | |
| reviewed_note | text | yes | | |
| promoted_channel_id | UUID | yes | | FK → channels; set when status flips to `approved` |
| run_id | text | yes | | Groups all candidates from one Scout run |

**Unique:** (platform, kind, external_id)
**Indexes:** status, kind, run_id, discovered_at DESC
**FK:** promoted_channel_id → channels.channel_id

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
| logo_url | text | yes | | Channel avatar / logo (mig 025) |
| handle | text | yes | | Platform handle — YouTube `@customUrl`, Twitter `@handle` (mig 033) |
| last_polled_at | timestamptz | yes | | |
| created_at | timestamptz | no | now() | |

**Indexes:** platform, active, handle (partial: WHERE handle IS NOT NULL)
**Unique:** slug; (platform, external_id)

---

### channel_metrics

Time-series popularity per channel. Multi-platform via the JSONB `metrics` column — YouTube uses `{subscribers, videos, views, country, channel_published_at}`; other platforms (podcast, twitter) carry their own shape. Identity stays clean in `channels`; popularity (which changes over time and varies per platform) lives here.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| metric_id | UUID | PK | uuid4 | |
| channel_id | UUID | no | | FK → channels (CASCADE) |
| platform | text | no | | Mirrors `channels.platform` at sample time |
| sampled_at | timestamptz | no | now() | |
| source | text | no | | `youtube_api`, `apple_podcasts`, `manual`, ... |
| metrics | jsonb | no | {} | Platform-specific shape |

**Unique:** (channel_id, sampled_at)
**Indexes:** (channel_id, sampled_at DESC), (platform, sampled_at DESC), sampled_at DESC

For "current state" queries (wiki cards, ranking) prefer the `channel_latest_metrics` view over scanning the table.

---

### sources

Individual content items (a specific video, episode, article).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| source_id | UUID | PK | uuid4 | |
| channel_id | UUID | yes | | FK → channels |
| source_type | text | no | | `youtube`, `podcast`, `web`, `radio`, `manual` |
| title | text | no | | |
| description | text | yes | | Full video/article description; chapter timestamps often live here (mig 033) |
| thumbnail_url | text | yes | | Best available thumbnail (YouTube high/maxres, podcast cover art) (mig 033) |
| duration_seconds | int | yes | | Length in seconds; constant per video, refreshed on stats sync (mig 033) |
| is_short | bool | yes | | **Generated column** — `duration_seconds IS NOT NULL AND duration_seconds < 60`. True for YouTube Shorts (mig 033) |
| creator_name | text | yes | | |
| canonical_url | text | yes | | unique |
| approved_flag | bool | no | false | |
| ingestion_status | text | no | `pending` | |
| published_at | timestamptz | yes | | |
| ingested_at | timestamptz | yes | | |
| created_at | timestamptz | no | now() | |

**Indexes:** source_type, approved_flag, is_short (partial: WHERE is_short=true), duration_seconds (partial: WHERE NOT NULL)
**Unique:** canonical_url
**FK:** channel_id → channels.channel_id

---

### video_metrics

Time-series popularity per video (a `sources` row). Same shape as `channel_metrics` — see migration 023 for the design rationale. YouTube payload: `{views, likes, comments, duration_seconds}`. Sampled at video discovery time and weekly thereafter via the admin refresh endpoint.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| metric_id | UUID | PK | uuid4 | |
| source_id | UUID | no | | FK → sources (CASCADE) |
| sampled_at | timestamptz | no | now() | |
| source | text | no | | `youtube_api`, `manual`, ... |
| metrics | jsonb | no | {} | Platform-specific shape |

**Unique:** (source_id, sampled_at)
**Indexes:** (source_id, sampled_at DESC), sampled_at DESC

For "current state" queries prefer the `video_latest_metrics` view.

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

### source_speakers

Diarised speaker turns over a document. Coarse-grained span layer above `source_chunks`; chunks fall within a speaker turn by timestamp containment. Populated by the diarisation pass (Deepgram or equivalent) after document ingest.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| segment_id | UUID | PK | uuid4 | |
| document_id | UUID | no | | FK → source_documents (CASCADE) |
| speaker_entity_id | UUID | yes | | FK → entities (typically `expert`/`advisor`); NULL for unattributed turns |
| speaker_label | text | yes | | Raw diariser label (`Speaker 1`) when entity not yet resolved |
| start_ts | float | no | | Seconds |
| end_ts | float | no | | Seconds |
| confidence | float | yes | | Diarisation confidence 0-1 |
| created_at | timestamptz | no | now() | |

**Indexes:** document_id, speaker_entity_id, (document_id, start_ts)
**FK:** document_id → source_documents (CASCADE); speaker_entity_id → entities

---

### source_chapters

Semantic chapters detected over a document. Used by the analyse-transcript pipeline to scope claim extraction and to attribute claims back to a chapter for UI navigation.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| chapter_id | UUID | PK | uuid4 | |
| document_id | UUID | no | | FK → source_documents (CASCADE) |
| ordinal | int | no | | Order within document |
| title | text | no | | Short label |
| summary | text | yes | | Agent-written summary |
| start_ts | float | no | | |
| end_ts | float | no | | |
| created_at | timestamptz | no | now() | |

**Unique:** (document_id, ordinal)
**Indexes:** document_id, (document_id, start_ts)
**FK:** document_id → source_documents (CASCADE)

---

### source_annotations

Generic descriptive overlay table. Use for sentiment, sub-topic tags, entity mentions, themes, and any future enrichment that doesn't warrant a first-class table.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| annotation_id | UUID | PK | uuid4 | |
| document_id | UUID | no | | FK → source_documents (CASCADE) |
| kind | text | no | | `sentiment`, `subtopic`, `mention`, `theme`, ... |
| start_ts | float | yes | | Span start; NULL for document-level annotations |
| end_ts | float | yes | | Span end |
| target_entity_id | UUID | yes | | FK → entities (e.g. for `mention` kind) |
| label | text | yes | | Short string value |
| payload_json | jsonb | no | {} | Kind-specific payload (sentiment scores, etc.) |
| confidence | float | yes | | |
| created_at | timestamptz | no | now() | |

**Indexes:** document_id, kind, target_entity_id, (document_id, kind)
**FK:** document_id → source_documents (CASCADE); target_entity_id → entities

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

## 4. Reasoning & output

What Jaromelu produces from the world (Layer 2) plus the content (Layer 3).

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

### events

Immutable audit trail of system activity. Entries are hashed for tamper detection.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| event_id | UUID | PK | uuid4 | |
| event_type | text | no | | |
| related_entity_ids | UUID[] | no | [] | |
| related_decision_id | UUID | yes | | FK → decisions |
| related_prediction_id | UUID | yes | | FK → predictions |
| related_claim_ids | UUID[] | no | [] | Claim ids this event references (no FK — array) |
| related_source_id | UUID | yes | | FK → sources |
| display_text | text | no | | |
| display_mode | text | no | | `watching`, `signal`, `thinking`, `prediction`, `action`, `review`, `sys`, `question`, `answer` |
| metadata_json | jsonb | no | {} | Free-form event payload |
| visibility | text | no | `public` | `public`, `private` |
| created_at | timestamptz | no | now() | |
| immutable_hash | text | yes | | SHA256 of event payload |

**Indexes:** event_type, created_at, visibility
**FK:** related_decision_id → decisions; related_prediction_id → predictions; related_source_id → sources

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

### remarks — planned (not yet built)

> **Status:** described below as planned design — not yet present in `models.py` or migrations. Will be revisited as the front-end build clarifies whether this stays a distinct table from `predictions`/`decisions`. See [docs/concepts/02-remarks.md](../concepts/02-remarks.md) for the design intent.

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

### remark_reactions — planned (not yet built)

> **Status:** described below as planned design — depends on `remarks`.

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

### alignment_scores — planned (not yet built)

> **Status:** described below as planned design — not yet present in `models.py` or migrations. Will be built when the Ledger surface lights up.

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

Prose per-entity (or per-channel) knowledge pages, written and maintained by a managed agent.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| page_id | UUID | PK | uuid4 | |
| entity_id | UUID | yes | | FK → entities (set for entity-typed pages) |
| channel_id | UUID | yes | | FK → channels (set for `channel`-typed pages, mig 019) |
| page_type | text | no | | `player`, `team`, `advisor`, `round`, `channel` |
| slug | text | no | | URL slug, unique |
| title | text | no | | Display name |
| content | text | no | "" | Markdown with `[[slug]]` wiki-links |
| summary | text | yes | | One-liner for listings |
| metadata_json | jsonb | no | {} | Tags, sidebar data |
| status | text | no | `stub` | `stub`, `draft`, `published` |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | Auto-updates |

**Unique:** slug
**Check:** exactly one of `entity_id` / `channel_id` is set
**Indexes:** page_type, slug, entity_id, channel_id, updated_at, status
**FK:** entity_id → entities; channel_id → channels

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

### squad_slots, squad_trades — planned (SuperCoach squad feature)

Reserved for the upcoming SuperCoach squad management feature; schema is in place but not yet wired up by the live app. Will hold the user's active squad and trade history once the SuperCoach component lands. See [architecture/04-information-architecture.md](../architecture/04-information-architecture.md).

---

## 5. Agent audit

Per-run and per-event observability for Claude-Agent-SDK-based agents (Scout, Scribe, Analyst, Stats, Fixtures). Live-queryable store while a run is in flight; the same events also serialise to JSONL and upload to S3 at run end for long-term forensics. Powers run dashboards, cost roll-ups, and post-hoc replay. See [docs/agents/system/agent-audit.md](../agents/system/agent-audit.md) for the full audit pattern.

### agent_runs

Run-level summary. One row per run, keyed by `run_id`. Inserted with `status='running'` at the top of a run and updated in place at run end with totals, summary, and cost rollup. Joined to `agent_events` (the per-event trail) via `run_id`.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| run_id | text | PK | | |
| agent_id | text | no | | `scout`, `scribe`, `analyst`, `stats`, `fixtures` |
| agent_name | text | no | | |
| status | text | no | `running` | `running`, `completed`, `aborted`, `failed` |
| started_at | timestamptz | no | now() | |
| ended_at | timestamptz | yes | | |
| model | text | yes | | Claude model id |
| brief_preview | text | yes | | First N chars of the run brief |
| bounds_json | jsonb | no | {} | Run bounds (max turns, budget) |
| summary | text | no | "" | Filled at run end |
| detail_json | jsonb | no | {} | |
| s3_log_key | text | yes | | S3 key for the JSONL event upload |
| agent_events_count | int | yes | | Total events written to `agent_events` |
| turns_used | int | yes | | |
| tool_calls | int | yes | | |
| input_tokens | int | yes | | |
| output_tokens | int | yes | | |
| cache_read_tokens | int | yes | | |
| cache_write_tokens | int | yes | | |
| token_cost_usd | numeric(12,6) | yes | | Estimated, not invoiced |
| server_tool_cost_usd | numeric(12,6) | yes | | |
| total_cost_usd | numeric(12,6) | yes | | |

**Indexes:** (agent_id, started_at DESC), started_at DESC, started_at DESC WHERE status='running' (partial)

Token columns are rolled up from `agent_events.payload->'usage'`. Cost columns are estimated via `jeromelu_shared.agent_audit.estimate_*` — used for budget gates and observability, not invoicing.

---

### agent_events

Per-event audit trail. One row per event in an agent run; dense `sequence` per run for ordered replay. Joined to `agent_runs` via `run_id`.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| event_id | UUID | PK | uuid4 | |
| run_id | text | no | | Joins to `agent_runs.run_id` |
| agent_id | text | no | | |
| sequence | int | no | | 0-indexed, dense, per-run |
| t | timestamptz | no | now() | |
| type | text | no | | `run_started`, `turn_started`, `text`, `tool_use`, `tool_result`, `server_block`, `turn_complete`, `bound_hit`, `error`, `run_ended` |
| turn | int | yes | | NULL on lifecycle events (e.g. `run_started`) |
| payload | jsonb | no | {} | Type-specific payload (text body, tool input/output, usage, etc.) |

**Unique:** (run_id, sequence)
**Indexes:** (run_id, sequence), (agent_id, t DESC), type

Ten standard event types defined in `jeromelu_shared.agent_audit`.

---

## 6. Deprecated / removed

### player_team_history

Dropped in migration 027. Replaced by `player_attributes` (SCD-2), which holds team affiliation alongside primary position, height/weight, and contract data on a single row per current state.

---

## Appendix A: `player_rounds` full column list

The full ~60-column shape of `player_rounds`. Unique key is `(player_id, round, season)`; FKs are `match_id → matches` and `team_id → teams` (both nullable, populated for new writes after migration 032).

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
| opposition | text | yes | | Legacy free-text — pre-mig 032 rows |
| venue | text | yes | | Legacy free-text — pre-mig 032 rows |
| weather | text | yes | | |
| surface | text | yes | | |
| jersey | int | yes | | Jersey number |
| bye_round | text | yes | | |
| **Canonical FKs (mig 032)** | | | | |
| match_id | UUID | yes | | FK → matches; new writes only |
| team_id | UUID | yes | | FK → teams; new writes only |
| created_at | timestamptz | no | now() | |

---

## Appendix B: Migrations

Authoritative list: [`packages/db/migrations/`](../../packages/db/migrations/). Each filename describes the change; read the SQL for detail.

When a migration lands:

1. Update the affected table section above.
2. Update the schema overview diagram if the topology changed.
3. Remove any *(proposed)* markers on items the migration realised.
