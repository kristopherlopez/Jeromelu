---
tags: [area/operations]
---

# Data Catalogue

Personal reference for the Jaromelu data model. Source of truth: `packages/shared/jeromelu_shared/db/models.py`

The schema breaks into five layers:

- **Identity** — typed per-kind tables for things claims/predictions/wiki reference: `people`, `people_attributes`, `people_roles`, `rounds`. Pre-mig-038 this was a single polymorphic `entities` table — now retired.
- **Structured world** — Real things and their facts: teams, venues, fixtures, rosters, injuries, per-round stats.
- **Content & claims** — Pipeline from channel → source → document → overlays → quote → claim, plus time-series popularity sidecars.
- **Reasoning & output** — What Jaromelu produces from the world plus the content: predictions, decisions, remarks, alignment scores, knowledge base, wiki. Cross-type subjects modelled as typed-FK association junctions (`claim_associations`, etc.).
- **Agent audit** — Per-run and per-event observability for Claude-Agent-SDK-based agents.

---

## Schema Overview

```
Layer 1 — IDENTITY ─────────────────────────────────────────────────────────────
   ┌──────────────┐        ┌────────────────────┐        ┌──────────────┐
   │    people    │──────▶ │ people_attributes  │        │    rounds    │
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
   scout_candidates ──(promote)──▶ channels / sources    (Scout's review queue)
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

`*_associations` tables are typed-nullable-FK + CHECK exactly-one junctions. Each row points at one of `person_id` / `team_id` / `match_id` / `venue_id` / `round_id` — replaces the old polymorphic `subject_entity_id` UUID. See [refactor-entities-to-typed-tables](refactor-entities-to-typed-tables.md) for the full design rationale (executed in migrations 036–038).

---

## 1. Identity

The noun layer. People, rounds — the things claims, predictions, decisions, wiki pages, etc. reference. Pre-mig-038 this was a single polymorphic `entities` table with a denormalised `entity_type` column; after the refactor it's typed-per-kind with specific tables. Teams / venues / matches live in §2 (Structured world) since they carry significant per-type facts.

### people

Unified table for every human actor — players, coaches, advisors, commentators, journalists, referees. Lifetime-stable facts get typed columns; long-tail goes in `metadata_json`.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| person_id | UUID | PK | uuid4 | |
| canonical_name | text | no | | |
| aliases | text[] | no | `{}` | Alternative names/spellings |
| slug | text | yes | | UNIQUE; URL-safe slug |
| dob | date | yes | | Date of birth |
| country | text | yes | | `AU`, `NZ`, `UK`, `PNG`, ... |
| image_url | text | yes | | Profile/headshot URL |
| supercoach_id | int | yes | | UNIQUE; cross-system identifier (NULL for non-players) |
| metadata_json | jsonb | no | {} | Long-tail / sparse / unstructured (twitter handle, wikipedia URL, etc.) |
| created_at | timestamptz | no | now() | |

**Unique:** slug, supercoach_id
**Indexes:** canonical_name, country (partial: WHERE NOT NULL)

---

### people_attributes

SCD-2 of slow-changing per-person facts (team affiliation, primary position, height/weight, contract). Replaces the old `player_attributes` table. Closed and reopened on change.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| person_id | UUID | no | | FK → people (CASCADE) |
| team_id | UUID | yes | | FK → teams (SET NULL); parent NRL/NRLW row even when player is on a feeder grade |
| primary_position | text | yes | | SC position string (FRF, HOK, HFB, ...) |
| height_cm | int | yes | | |
| weight_kg | int | yes | | |
| contract_until | date | yes | | Real-world contract end |
| real_salary_aud | int | yes | | Reserved for future feed; NULL today |
| metadata_json | jsonb | no | {} | secondary_positions etc. (long-tail; promote to columns when heavily queried) |
| effective_from | date | no | | Start of this state |
| effective_to | date | yes | | End of state (NULL = current) |
| is_current | bool | no | true | |
| source | text | no | `seed` | `supercoach`, `nrl_com`, `nswrl_com`, `qrl_com`, `seed`, ... |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | Auto-updates |

**Indexes:** (person_id, is_current), (team_id, is_current)
**Unique partial index:** person_id WHERE is_current — exactly one current row per person
**Check:** `effective_to IS NULL OR effective_to >= effective_from`
**FK:** person_id → people (CASCADE); team_id → teams (SET NULL)

Lifetime constants (dob, country) live on `people`; per-round facts (price, breakeven, score, jersey, grade) live on `player_rounds`.

---

### people_roles

SCD-2 of role tenure per person. **Multi-valued at a single point in time** — a person can hold multiple roles concurrently (Adam Reynolds = active player + occasional commentator) or transition (Andrew Johns: player → commentator). Replaces `entity_roles`.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| role_id | UUID | PK | uuid4 | |
| person_id | UUID | no | | FK → people (CASCADE) |
| role | text | no | | `player`, `coach`, `commentator`, `journalist`, `referee`, `advisor` |
| effective_from | date | no | | Start of tenure |
| effective_to | date | yes | | End of tenure (NULL = current) |
| is_primary | bool | no | false | Exactly one primary current row per person |
| metadata_json | jsonb | no | {} | |
| source | text | no | `seed` | `seed`, `backfill_036`, `manual`, ... |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | |

**Indexes:** (person_id, effective_to), (role, effective_from, effective_to)
**Unique partial index:** person_id WHERE is_primary AND effective_to IS NULL — exactly one primary current role per person
**Check:** `effective_to IS NULL OR effective_to >= effective_from`
**FK:** person_id → people (CASCADE)

To filter "current commentators": `WHERE role='commentator' AND is_primary AND effective_to IS NULL`. There is no denormalised `people.entity_type` — JOIN to this table when you need the role.

---

### rounds

Round identity for the NRL/NRLW competition cycles. Referenced by claim/prediction/decision associations when an opinion is round-level rather than player- or match-level.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| round_id | UUID | PK | uuid4 | |
| season | int | no | | |
| round_number | int | yes | | NULL for finals — use `round_label` |
| round_label | text | no | | "Round 5", "Finals Week 1", "Magic Round" |
| starts_at | timestamptz | yes | | |
| ends_at | timestamptz | yes | | |
| is_magic_round | bool | no | false | |
| is_rep_weekend | bool | no | false | |
| is_finals | bool | no | false | |
| metadata_json | jsonb | no | {} | |

**Unique:** (season, round_number)
**Indexes:** season

---

## 2. Structured world

Real-world rows holding facts. Cross-type references from claims/predictions/etc. point here via the typed FK columns on association junctions (see §4).

### teams

Canonical roster of every team across all grades feeding into NRL — NRL,
NRLW, NSW Cup, QLD Cup (Hostplus Cup), and the junior pathway grades
(Jersey Flegg, Mal Meninga, SG Ball, Cyril Connell, Harold Matthews —
schema-allowed; not yet seeded). `parent_team_id` self-references to link
a feeder team to its senior NRL/NRLW side.

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
| founded_year | int | yes | | |
| logo_url | text | yes | | |
| metadata_json | jsonb | no | {} | Long-tail: nicknames, fan_club_url, naming_history, optional home_venue_id, optional primary_colour / secondary_colour, expansion-team `enters_competition_year`, etc. |
| active | bool | no | true | |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | Auto-updates |

**Unique:** slug
**Indexes:** grade, parent_team_id, active
**FK:** parent_team_id → teams (ON DELETE SET NULL)

Baseline seed for prod and local lives in migration `039_seed_teams_2026.sql` — 19 NRL (incl. Perth Bears 2027 and Papua New Guinea 2028 expansion sides flagged via `metadata_json.enters_competition_year`), 12 NRLW, 12 NSW Cup, 15 Hostplus Cup. Idempotent (`ON CONFLICT (slug) DO UPDATE`). Pathway grades (Jersey Flegg, SG Ball, Mal Meninga, Cyril Connell, Harold Matthews) are schema-allowed but not yet seeded — populate via a follow-up migration once a downstream consumer needs them.

Incremental top-ups (e.g. when PNG's team name is announced, or when a feeder affiliation changes) go via the admin endpoint `POST /api/admin/teams/seed` (`make prod-seed-teams`) which takes a yaml-shaped JSON payload and runs the same idempotent upsert against `jeromelu_shared.teams.seed_teams()`.

#### Historical lineage — potential future update

Today's `teams` schema captures *current* clubs. As historical content lights up (defunct sides like North Sydney Bears NRL 1908–1999, Newtown Jets NRL pre-1983, Adelaide Rams, Western Reds, etc.; mergers like Balmain + Western Suburbs → Wests Tigers; competition renames NSWRFL → NSWRL → ARL → NRL), three concerns surface:

- **Defunct clubs** — currently expressed via `active=false` only.
- **Mergers** — predecessor / successor relationships have no first-class home.
- **Competition rename** — `teams.competition` is a single text label and assumes one comp per club for all time.

**Interim convention** (until a downstream feature actually queries this): use `metadata_json` keys on existing rows.
- `lifespan: [{competition: "NRL", from: 1908, to: 1999}, {competition: "NSW Cup", from: 2007}]` — array of stints in chronological order.
- `predecessor_slugs: ["balmain_tigers", "western_suburbs_magpies"]` on the merged-into row.
- `successor_slugs: ["wests_tigers"]` on the merged-out rows.
- Treat `NSWRFL → NSWRL → ARL → NRL` as a small hardcoded constant in code; store the contemporaneous comp name inside `lifespan[].competition` rather than upgrading the schema.

**Upgrade path** when the interim shape stops paying its way: introduce a temporal SCD-2 `team_competitions` table (team_id, competition_id, effective_from, effective_to) plus a `competitions` reference (id, name, founded, ended, succeeded_by) seeded with NSWRFL, NSWRL, ARL, NRL, NRLW, NSW Cup, QLD Cup. Triggers for the upgrade: a feature that queries "teams active in NRL season X", >50 historical rows where typo tolerance matters, or any UI showing year-by-year competition membership. At that point `teams.competition` retires (becomes derivable as the current `team_competitions` row).

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
| latitude | numeric(9,6) | yes | | |
| longitude | numeric(9,6) | yes | | |
| opened_year | int | yes | | |
| image_url | text | yes | | |
| metadata_json | jsonb | no | {} | Long-tail (transport_links, parking_capacity, naming_history) |
| active | bool | no | true | |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | Auto-updates |

**Unique:** slug
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
| home_team_id | UUID | no | | FK → teams (RESTRICT). For bye rows: the team in question (column name overloaded). |
| away_team_id | UUID | yes | | FK → teams (RESTRICT). NULL for bye rows. |
| venue_id | UUID | yes | | FK → venues (SET NULL) |
| kickoff_at | timestamptz | yes | | UTC; render in `venues.tz`. NULL for bye rows. |
| status | text | no | `scheduled` | `scheduled`, `live`, `final`, `postponed`, `cancelled`, `forfeit`, `bye` |
| home_score | int | yes | | Paired — both NULL or both set |
| away_score | int | yes | | |
| weather | text | yes | | |
| referee_name | text | yes | | |
| broadcast | text | yes | | |
| is_magic_round | bool | no | false | |
| is_rep_weekend | bool | no | false | |
| metadata_json | jsonb | no | {} | Ladder context, broadcast quirks, score corrections |
| last_synced_at | timestamptz | yes | | When the fixture-sync last touched this row |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | Auto-updates |

**Unique:** (source, season, grade, external_match_id) — partial, only when external_match_id is set
**Indexes:** (season, round, grade), kickoff_at, status, home_team_id, away_team_id, venue_id
**Constraints:** home_team_id ≠ away_team_id; scores paired; `(status='bye' AND away_team_id IS NULL) OR (status<>'bye' AND away_team_id IS NOT NULL)` (`ck_matches_bye_no_opponent`)
**FK:** home_team_id, away_team_id → teams.team_id (RESTRICT); venue_id → venues.venue_id (SET NULL)

Populated by the daily fixture-sync against the NRL.com draw API (see `docs/agents/system/scraper.md`).

**Bye rows:** `status='bye'` indicates a bye for `home_team_id` (the column is semantically overloaded for byes — it just means "the team in question," not literally "home team"). `away_team_id`, `kickoff_at`, scores, weather, broadcast are all NULL. Match queries that don't want byes filter `WHERE status<>'bye'` or `WHERE away_team_id IS NOT NULL`.

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
| player_id | UUID | no | | FK → people (RESTRICT) |
| jersey_number | int | yes | | 1..30 (allows reserves) |
| named_position | text | yes | | `fullback`, `wing`, `centre`, `five-eighth`, `halfback`, `hooker`, `prop`, `second-row`, `lock`, `interchange`, `reserve` |
| sc_position | text | yes | | SC position string (HOK/HFB/CTW/FRF/2RF/MID/FLB/FLX) — populated when the SC API is the source |
| is_captain | bool | no | false | Per-match-per-player captain flag (mig 036). |
| list_version | int | no | 1 | Monotonically increasing per (match, team) |
| status | text | no | `named` | `named`, `late_change_in`, `late_change_out`, `19th_man`, `reserve`, `withdrawn` |
| announced_at | timestamptz | yes | | |
| source | text | no | `nrl_com` | |
| metadata_json | jsonb | no | {} | |
| created_at | timestamptz | no | now() | |

**Unique:** (match_id, team_id, player_id, list_version)
**Indexes:** match_id, team_id, player_id, (match_id, team_id, list_version DESC)
**FK:** match_id → matches (CASCADE); team_id → teams (RESTRICT); player_id → people (RESTRICT)

Live current state for a fixture: filter by (match_id, team_id) and pick `list_version` DESC.

---

### injuries

Append-on-change timeline of player injury / suspension state. Each daily
casualty-ward sweep writes a new row only when a player's status has
actually changed (or appeared for the first time).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| injury_id | UUID | PK | uuid4 | |
| player_id | UUID | no | | FK → people (CASCADE) |
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

**Indexes:** (player_id, reported_at DESC), (team_id, status) WHERE resolved_at IS NULL, reported_at
**FK:** player_id → people (CASCADE); team_id → teams (SET NULL)

"Latest known status for player X": ORDER BY reported_at DESC LIMIT 1.

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
| speaker_person_id | UUID | yes | | FK → people (SET NULL); NULL for unattributed turns |
| speaker_label | text | yes | | Raw diariser label (`Speaker 1`) when person not yet resolved |
| start_ts | float | no | | Seconds |
| end_ts | float | no | | Seconds |
| confidence | float | yes | | Diarisation confidence 0-1 |
| created_at | timestamptz | no | now() | |

**Indexes:** document_id, speaker_person_id (partial: WHERE NOT NULL), (document_id, start_ts)
**FK:** document_id → source_documents (CASCADE); speaker_person_id → people (SET NULL)

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

### quotes

Direct quotes extracted from source documents, attributed to a speaker.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| quote_id | UUID | PK | uuid4 | |
| document_id | UUID | no | | FK → source_documents |
| chunk_id | UUID | yes | | FK → source_chunks |
| speaker_person_id | UUID | yes | | FK → people |
| quoted_text | text | no | | |
| start_offset | int | yes | | Character offset |
| end_offset | int | yes | | Character offset |
| said_at_reference | text | yes | | Temporal reference in source |
| confidence | float | yes | | Extraction confidence 0-1 |
| created_at | timestamptz | no | now() | |

**Indexes:** document_id, speaker_person_id
**FK:** document_id → source_documents; chunk_id → source_chunks; speaker_person_id → people

---

### claims

The single extraction table — every assertion or annotation pulled from a transcript span. Mig 036 absorbed the old `source_annotations` table by expanding `claim_type` to include annotation-flavoured kinds. Subjects are not stored on the claim row itself; they're rows in `claim_associations` (see §4) with `role='subject'`.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| claim_id | UUID | PK | uuid4 | |
| document_id | UUID | yes | | FK → source_documents |
| quote_id | UUID | yes | | FK → quotes |
| claim_type | text | no | | Fantasy-actionable: `buy`, `sell`, `hold`, `captain`, `avoid`, `breakout`, `matchup_edge`. Annotation-flavoured (mig 036): `mention`, `theme`, `subtopic`, `sentiment`, `tactical_tag`, `highlight`. |
| claim_text | text | yes | | Human-readable summary |
| polarity | float | yes | | Positive/negative sentiment |
| strength | float | yes | | Conviction level |
| effective_round | int | yes | | NRL round this applies to |
| season | int | yes | | NRL season year |
| start_ts | float | yes | | Video timestamp start (seconds) |
| end_ts | float | yes | | Video timestamp end (seconds) |
| payload_json | jsonb | no | {} | Kind-specific payload (sentiment scores, sub-topic metadata, etc.) |
| extracted_at | timestamptz | no | now() | |

**Indexes:** claim_type, document_id, (effective_round, season)
**FK:** document_id → source_documents; quote_id → quotes

Subjects: query `claim_associations WHERE claim_id = X AND role = 'subject'` to dispatch on which typed FK is set (person/team/match/venue/round). The fantasy-claim use case filters by `claim_type IN ('buy','sell','hold','captain','avoid','breakout','matchup_edge')`.

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

### claim_associations

Polymorphic many-to-many between claims and typed entities. A claim can name multiple typed subjects with different roles (e.g. a player as the subject + a team as context). The CHECK constraint enforces exactly one typed FK is set per row.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| association_id | UUID | PK | uuid4 | |
| claim_id | UUID | no | | FK → claims (CASCADE) |
| role | text | no | | `subject`, `context`, `opponent`, `mentioned`, ... |
| person_id | UUID | yes | | FK → people (CASCADE) |
| team_id | UUID | yes | | FK → teams (CASCADE) |
| match_id | UUID | yes | | FK → matches (CASCADE) |
| venue_id | UUID | yes | | FK → venues (CASCADE) |
| round_id | UUID | yes | | FK → rounds (CASCADE) |

**Check:** `(person_id IS NOT NULL)::int + (team_id IS NOT NULL)::int + (match_id IS NOT NULL)::int + (venue_id IS NOT NULL)::int + (round_id IS NOT NULL)::int = 1` (`ck_claim_associations_one_subject`)
**Unique:** (claim_id, role, person_id, team_id, match_id, venue_id, round_id) NULLS NOT DISTINCT
**Indexes:** claim_id, plus per-FK partial indexes WHERE NOT NULL

---

## 4. Reasoning & output

What Jaromelu produces from the world (Layer 2) plus the content (Layer 3).

### predictions

Forecasts about future events, linked to evidence claims. Subject(s) live on `prediction_associations`.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| prediction_id | UUID | PK | uuid4 | |
| predictor_person_id | UUID | yes | | FK → people (who made the prediction) |
| prediction_type | text | yes | | |
| predicted_value_text | text | yes | | |
| event_window | text | yes | | e.g. "Round 5", "2026 season" |
| evidence_claim_ids | UUID[] | no | [] | Array of claim_ids backing this |
| created_at | timestamptz | no | now() | |
| resolved_at | timestamptz | yes | | When outcome was determined |
| resolution_status | text | yes | | |

**Indexes:** predictor_person_id
**FK:** predictor_person_id → people

---

### prediction_associations

Polymorphic many-to-many between predictions and typed entities. Same shape as `claim_associations` (§3) — one row with `role='subject'` per prediction is the dominant case.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| association_id | UUID | PK | uuid4 | |
| prediction_id | UUID | no | | FK → predictions (CASCADE) |
| role | text | no | | `subject`, `context`, `opponent`, ... |
| person_id | UUID | yes | | FK → people (CASCADE) |
| team_id | UUID | yes | | FK → teams (CASCADE) |
| match_id | UUID | yes | | FK → matches (CASCADE) |
| venue_id | UUID | yes | | FK → venues (CASCADE) |
| round_id | UUID | yes | | FK → rounds (CASCADE) |

**Check:** exactly-one of typed FKs (`ck_prediction_associations_one_subject`)
**Unique:** (prediction_id, role, person_id, team_id, match_id, venue_id, round_id) NULLS NOT DISTINCT
**Indexes:** prediction_id, plus per-FK partial indexes WHERE NOT NULL

---

### consensus_snapshots

Aggregated claim sentiment for a typed subject at a point in time. Exactly one of `person_id` / `team_id` / `match_id` / `venue_id` / `round_id` is set per row.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| snapshot_id | UUID | PK | uuid4 | |
| person_id | UUID | yes | | FK → people |
| team_id | UUID | yes | | FK → teams |
| match_id | UUID | yes | | FK → matches |
| venue_id | UUID | yes | | FK → venues |
| round_id | UUID | yes | | FK → rounds |
| time_bucket | timestamptz | no | | Aggregation window |
| buy_count | int | no | 0 | |
| sell_count | int | no | 0 | |
| hold_count | int | no | 0 | |
| neutral_count | int | no | 0 | |
| contrarian_score | float | yes | | |
| consensus_score | float | yes | | |
| created_at | timestamptz | no | now() | |

**Check:** exactly-one of typed FKs (`ck_consensus_snapshots_subject`)
**Indexes:** (person_id, time_bucket)
**FK:** person_id → people; team_id → teams; match_id → matches; venue_id → venues; round_id → rounds

---

### decisions

Action decisions made in the system (trades, captain picks, etc.). Subject(s) and contextual entities live on `decision_associations`.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| decision_id | UUID | PK | uuid4 | |
| decision_type | text | no | | `trade`, `captain`, `start_sit`, `squad_structure`, `article_topic`, `reply` |
| action_json | jsonb | no | {} | Structured action payload |
| rationale_summary | text | yes | | |
| strategy_tag | text | yes | | |
| created_at | timestamptz | no | now() | |
| executed_at | timestamptz | yes | | |
| public_flag | bool | no | false | |

**Indexes:** decision_type

---

### decision_associations

Polymorphic many-to-many between decisions and typed entities. Trade decisions typically have `role='player_in'` and `role='player_out'` rows pointing at people; captain decisions have one `role='subject'` person; etc.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| association_id | UUID | PK | uuid4 | |
| decision_id | UUID | no | | FK → decisions (CASCADE) |
| role | text | no | | `subject`, `player_in`, `player_out`, `context`, ... |
| person_id | UUID | yes | | FK → people (CASCADE) |
| team_id | UUID | yes | | FK → teams (CASCADE) |
| match_id | UUID | yes | | FK → matches (CASCADE) |
| venue_id | UUID | yes | | FK → venues (CASCADE) |
| round_id | UUID | yes | | FK → rounds (CASCADE) |

**Check:** exactly-one of typed FKs (`ck_decision_associations_one_subject`)
**Unique:** (decision_id, role, person_id, team_id, match_id, venue_id, round_id) NULLS NOT DISTINCT
**Indexes:** decision_id, plus per-FK partial indexes WHERE NOT NULL

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

> **Status:** described below as planned design — not yet present in `models.py` or migrations. Will be revisited as the front-end build clarifies whether this stays a distinct table from `predictions`/`decisions`. See [docs/concepts/02-remarks.md](../concepts/02-remarks.md) for the design intent. Subjects will use a `remark_associations` junction following the same Option-B shape as `claim_associations`.

The atomic output unit: an opinionated, voiced analytical piece with an open → locked → resolved lifecycle.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| remark_id | UUID | PK | uuid4 | |
| voice_text | text | no | | Jaromelu's voiced output |
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

Subjects (players/teams/matches/venues/rounds the remark is about) live on a planned `remark_associations` junction with the same shape as `claim_associations`.

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

> **Status:** described below as planned design — not yet present in `models.py` or migrations. Will be built when the Ledger surface lights up. Subject will use typed-nullable FKs + CHECK exactly-one (same Option-B pattern as `claim_associations`) — likely just `person_id` since alignment is per-human.

Prediction accuracy tracking per person (expert, user, or system). Powers [The Ledger](../pages/ledger/overview.md)'s Alignment Index.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| score_id | UUID | PK | uuid4 | |
| person_id | UUID | no | | FK → people |
| entity_type | text | no | | `expert`, `user`, `system` |
| score_type | text | no | | `overall`, `captain_picks`, `buy_sell`, `matchup` |
| period | text | no | | `round`, `month`, `season` |
| period_value | text | yes | | e.g. round number or season year |
| total_predictions | int | no | 0 | |
| correct_predictions | int | no | 0 | |
| alignment_pct | float | yes | | |
| updated_at | timestamptz | no | now() | |

**Indexes:** (person_id, score_type, period, period_value)
**FK:** person_id → people

---

### knowledge_base

Distilled, structured knowledge chunks embedded for RAG retrieval. Also stores Analysis articles.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| kb_id | UUID | PK | uuid4 | |
| kb_type | text | no | | `player_summary`, `round_brief`, `decision`, `opinion`, `source_digest`, `article_tips`, `article_totw`, `article_trades`, `article_captains`, `article_stocks`, `article_consensus` |
| person_id | UUID | yes | | FK → people |
| team_id | UUID | yes | | FK → teams |
| match_id | UUID | yes | | FK → matches |
| venue_id | UUID | yes | | FK → venues |
| round_id | UUID | yes | | FK → rounds |
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

**Check:** at-most-one of typed FKs (`ck_knowledge_base_subject`) — subject is optional (round_brief / source_digest / article_* kinds have no subject)
**Indexes:** kb_type, (effective_round, season), person_id, embedding (HNSW / IVFFlat)
**FK:** person_id → people; team_id → teams; match_id → matches; venue_id → venues; round_id → rounds

Powers [Ask Me](../pages/ask-me/overview.md) (RAG) and [The Analysis](../pages/analysis/overview.md) (`article_*` types).

---

### wiki_pages

Prose per-entity (or per-channel) knowledge pages, written and maintained by a managed agent.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| page_id | UUID | PK | uuid4 | |
| person_id | UUID | yes | | FK → people |
| team_id | UUID | yes | | FK → teams |
| match_id | UUID | yes | | FK → matches |
| venue_id | UUID | yes | | FK → venues |
| round_id | UUID | yes | | FK → rounds |
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
**Check:** exactly-one of person_id / team_id / match_id / venue_id / round_id / channel_id is set (`ck_wiki_page_subject`)
**Indexes:** page_type, slug, channel_id, updated_at, status
**FK:** person_id → people; team_id → teams; match_id → matches; venue_id → venues; round_id → rounds; channel_id → channels

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

Reserved for the upcoming SuperCoach squad management feature; tables exist but their player FK columns were dropped in mig 038 (they referenced the now-gone `entities` table). Player references return as typed FKs (`player_id` → people) when the SuperCoach feature is built. See [architecture/04-information-architecture.md](../architecture/04-information-architecture.md).

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

Dropped in migration 027. Replaced by `player_attributes` (mig 027) and subsequently by `people_attributes` (mig 038).

### entities

Dropped in migration 038. The polymorphic identity hub is replaced by typed per-kind tables: `people` (humans), `rounds` (NRL fixture rounds), and the existing structured-world tables (`teams`, `venues`, `matches`). Cross-type references that previously used `entity_id` go through typed-FK association junctions (`claim_associations`, `prediction_associations`, `decision_associations`) or direct typed FKs (`speaker_person_id`, `predictor_person_id`, `player_id`, etc.).

### entity_roles

Dropped in migration 038. Replaced by `people_roles` — same SCD-2 shape with `person_id` FK to `people` instead of `entity_id` to `entities`.

### player_attributes

Dropped in migration 038. Replaced by `people_attributes` — same SCD-2 shape with `person_id` FK to `people`. Generalised to any person role (not just players), though the dominant case is still players.

### source_annotations

Dropped in migration 036. Created in mig 034 (with no production rows), absorbed into a generalised `claims` table when it became clear annotations and claims were doing the same job. Annotation kinds (`mention`, `theme`, `subtopic`, `sentiment`, `tactical_tag`, `highlight`) became valid `claim_type` values; `payload_json` was added to `claims` for kind-specific payloads.

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

Recent landmarks worth knowing about:

- **036** — typed identity tables (`people`, `people_attributes`, `people_roles`, `rounds`) + association junctions (`claim_associations`, `prediction_associations`, `decision_associations`) added; `claims` absorbed `source_annotations`; `matches` accommodates byes; column promotions on teams/venues/matches; `is_captain` on `match_team_lists`.
- **037** — dropped two stale postgres-default-named CHECK constraints that conflicted with their `ck_*` replacements.
- **038** — dropped `entities`, `entity_roles`, `player_attributes`; dropped all polymorphic `*_entity_id` columns from output tables; tightened CHECK constraints on `wiki_pages` / `consensus_snapshots` / `knowledge_base` to enforce typed-FK exactly-one (or at-most-one for KB).

See [refactor-entities-to-typed-tables](refactor-entities-to-typed-tables.md) for the full design doc behind 036–038.

When a migration lands:

1. Update the affected table section above.
2. Update the schema overview diagram if the topology changed.
3. If the migration drops a table, move its description to §6 with a one-line note pointing at the replacement.
