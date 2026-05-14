---
tags: [area/architecture, area/operations]
---

# Data Lineage

> Created 2026-05-13. End-to-end view of where every piece of data in Jeromelu comes from, where it lands in S3, and how it eventually lands in the DB.
>
> **Per-table column-level lineage moved to [`docs/operations/data-lineage/`](../operations/data-lineage/README.md)** (2026-05-15). Each catalogue table now has its own file mapping every column to a source-profile JSON path + extractor. This document keeps the **conceptual** view: the L1→L2→L3 model, identity-resolution narrative, era coverage map, and downstream-surface map.
>
> The trinity:
> - [`docs/operations/data-sources/`](../operations/data-sources/README.md) — what's in S3 (upstream JSON profiles)
> - [`docs/operations/data-catalogue/`](../operations/data-catalogue/README.md) — what's in DB (column-level schema)
> - [`docs/operations/data-lineage/`](../operations/data-lineage/README.md) — the per-table mapping between them
>
> Other related docs:
> - [`docs/pages/wiki/data-feeds.md`](../pages/wiki/data-feeds.md) — wiki-centric "what feeds the wiki" view
> - [`docs/agents/crew/scout.md`](../agents/crew/scout.md) — Scout's pipeline inventory
> - [`docs/architecture/drafts/scout-charter-expansion.draft.md`](drafts/scout-charter-expansion.draft.md) — the charter governing all this
> - Per-pipeline `services/api/app/scout/{pipeline}/README.md` — implementation details

---

## Three layers

Every piece of structured NRL data in Jeromelu transits three layers:

```
┌──────────────────────────────────────────────────────────────┐
│ LAYER 1 — Source (external)                                  │
│   nrl.com · supercoach.com.au · nrlsupercoachstats.com        │
└──────────────────────────────────────────────────────────────┘
                       │  (Scout pipelines per D9)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 2 — S3 archive (durable, idempotent)                   │
│   s3://jeromelu-clean-documents/scout/{source}/{pipeline}/   │
│   Raw JSON snapshots. 8,940+ objects, 557 MB.                │
└──────────────────────────────────────────────────────────────┘
                       │  (Extractors, downstream per D13)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 3 — DB (queryable projection)                          │
│   people, teams, matches, match_team_lists, player_rounds,   │
│   player_match_stats, match_timeline, match_officials,       │
│   team_standings, stat_leaderboards, injuries, claims, …     │
└──────────────────────────────────────────────────────────────┘
                       │
                       ▼
                  App: wiki, feed, ask, ledger
```

**Key invariants:**

- L1 → L2: every fetch is idempotent (deterministic S3 key per identity). Re-runs overwrite the same key.
- L2 → L3: extractors are derived. Drop a DB table, replay extractors, the table comes back. No need to re-fetch L1.
- **L1 is never trusted as authoritative for derived facts** — L2 is. The trust hierarchy ([D11](drafts/scout-charter-expansion.draft.md)) is applied at extraction time, not capture time.

---

## Per-domain lineage

> **Note (2026-05-15):** the tables below are a frozen snapshot. Authoritative per-table lineage now lives at [`docs/operations/data-lineage/<table>.md`](../operations/data-lineage/README.md). Don't edit these tables in place — open the per-table file instead.

For each domain concept, we trace: **external source → Scout pipeline → S3 path → extractor → DB table(s)**.

### Players (identity layer)

| Field | Source | S3 archive | Extractor | DB target |
|---|---|---|---|---|
| `canonical_name`, `slug`, `aliases` | SC `players-cf` (first_name + last_name) | `scout/supercoach/classic/players-cf/{season}/{YYYYMMDD}.json` | `scout/supercoach_roster/` (shipped) | `people.canonical_name`, `.slug`, `.aliases` |
| `supercoach_id` | SC `players-cf` `id` | same as above | `scout/supercoach_roster/` | `people.supercoach_id` |
| `nrlcom_player_id` | nrl.com match-centre `players[].playerId`, players-data `playerId`, casualty `url` slug | `scout/nrlcom/match-centre/*` ⊕ `scout/nrlcom/players-roster/*` | Future extractor — name-match against `people` rows, set `people.nrlcom_player_id` | `people.nrlcom_player_id` (column added in migration 062) |
| `dob`, `country`, `image_url` | nrl.com `players-data` profile fields | `scout/nrlcom/players-roster/{comp}/team-{id}.json` | Existing `jeromelu_shared/players/nrlcom_refresh.py` (folder-organise as Phase 4.5) | `people.dob`, `.country`, `.image_url` |
| `position` (eligibility) | SC `players-cf` `positions[0]` (primary), `positions[]` (all eligible) | SC archive | `scout/supercoach_roster/` (existing) | `player_attributes.primary_position` (SCD-2); full list in `player_attributes.metadata_json.eligible_positions` |
| `team` (SCD-2) | SC `players-cf` `team.abbrev` → slug lookup | SC archive | `scout/supercoach_roster/` | `player_attributes.team_id` (SCD-2 close-current-open-new on diff) |
| Role tenure | SC roster (player), nrl.com match-centre coaches (coach), Analyst diarisation (advisor, future) | various | `scout/supercoach_roster/` (player); `scout/nrlcom_match_centre/` extractor (coach) | `people_roles` (one row per tenure window per role) |

**Identity-resolution note:** `people` is a **union** of all three external sources. The SC roster is the primary writer (550 current SC-eligible). nrlsupercoachstats expands the historical set (1,292 distinct 2018-2026). nrl.com match-centre adds anyone who's played a match since 2000 (potentially ~2,000 in total). Cross-source IDs are stored on the same `people` row as `supercoach_id` / `nrlcom_player_id`.

### Teams

| Field | Source | S3 archive | Extractor | DB target |
|---|---|---|---|---|
| `slug`, `name`, `short_name`, `aliases` | Seed scripts | n/a | `scripts/data/seed_teams.py` (one-shot) | `teams` (seeded once per season) |
| `nrlcom_team_id` | nrl.com match-centre `homeTeam.teamId` / `awayTeam.teamId`; `/draw/data` `filterTeams[].value` | `scout/nrlcom/draw/*` (filterTeams), `scout/nrlcom/match-centre/*` | Future extractor — name/short-name match | `teams.nrlcom_team_id` (column added in migration 062) |
| `metadata_json.supercoach` (SC id + abbrev + competition) | SC `/teams` endpoint | `scout/supercoach/classic/teams/{season}.json` | `scout/supercoach_teams/` (shipped) | `teams.metadata_json.supercoach = {id, abbrev, feed_name, name, competition}` |
| `logo_url`, `competition` | Seed + manual | — | — | `teams.logo_url`, `.competition` |

### Matches (the fixture spine)

| Field | Source | S3 archive | Extractor | DB target |
|---|---|---|---|---|
| `external_match_id` | nrl.com match-centre `matchId` | `scout/nrlcom/match-centre/*` | Future `extract_matches` | `matches.external_match_id` |
| `season`, `round`, `round_label` | nrl.com `/draw/data` filterRounds + match-centre `roundNumber`/`roundTitle` | `scout/nrlcom/draw/*` ⊕ `scout/nrlcom/match-centre/*` | `extract_matches` | `matches.season`, `.round`, `.round_label` |
| `home_team_id`, `away_team_id` | nrl.com `homeTeam.teamId` / `awayTeam.teamId` | match-centre | `extract_matches` (JOIN on `teams.nrlcom_team_id`) | `matches.home_team_id`, `.away_team_id` |
| `home_score`, `away_score` | nrl.com match-centre `homeTeam.score`, `awayTeam.score` | match-centre | `extract_matches` | `matches.home_score`, `.away_score` |
| `kickoff_at` | nrl.com `/draw/data` `clock.kickOffTimeLong` | draw | `extract_matches` | `matches.kickoff_at` |
| `venue_id` | nrl.com match-centre `venue` (text name) | match-centre | `extract_matches` (resolve venue name → `venues.slug`) | `matches.venue_id` |
| `weather`, `referee_name`, `broadcast` | match-centre `weather`, `officials[0]`, `broadcastChannels` | match-centre | `extract_matches` | `matches.weather`, `.referee_name`, `.broadcast` |
| `status` (`Pre`/`Live`/`Post`) | match-centre `matchMode` / `matchState` | match-centre | `extract_matches` | `matches.status` |
| `attendance`, `ground_conditions` | match-centre `attendance`, `groundConditions` | match-centre | `extract_matches` (after Tier 2 migration adds columns) | `matches.attendance`, `.ground_conditions` (future) |
| `metadata_json` | All match-centre fields not otherwise modeled (segments, broadcast, gameSeconds, etc.) | match-centre | `extract_matches` | `matches.metadata_json` |

### Match team lists (lineups)

Per [D11](drafts/scout-charter-expansion.draft.md) trust hierarchy + the captured shape:

| Field | Source | S3 archive | Extractor | DB target |
|---|---|---|---|---|
| `match_id` | Resolved from match-centre `matchId` | `scout/nrlcom/match-centre/*` | `extract_match_team_lists` | `match_team_lists.match_id` |
| `team_id` | `homeTeam.teamId` / `awayTeam.teamId` (via `teams.nrlcom_team_id`) | match-centre | extractor | `match_team_lists.team_id` |
| `player_id` | match-centre `homeTeam.players[].playerId` | match-centre | extractor — `JOIN people ON nrlcom_player_id` | `match_team_lists.player_id` |
| `jersey_number` | match-centre `homeTeam.players[].number` | match-centre | extractor | `match_team_lists.jersey_number` |
| `named_position` | match-centre `homeTeam.players[].position` ("Fullback", "Hooker", …) | match-centre | extractor | `match_team_lists.named_position` |
| `sc_position` | Future cross-ref to SC eligibility | SC archive | extractor | `match_team_lists.sc_position` |
| `is_captain` | match-centre `homeTeam.captainPlayerId == player.playerId` | match-centre | extractor | `match_team_lists.is_captain` |
| `list_version` | nrl.com lineup-snapshot date (Tue/Wed/Thu/late-change versions when modelled separately) | match-centre `updated` timestamp | extractor | `match_team_lists.list_version` |
| **Coaches** (Tier 2 — per user direction) | match-centre `homeTeam.coaches[]` | match-centre | extractor populates a `match_team_lists` row per coach: `jersey_number=NULL`, `named_position='Coach'` (or 'Assistant Coach'), `player_id=coach.profileId` (resolved via people.nrlcom_player_id) | `match_team_lists` (same table; coaches are first-class participants alongside players) |

### Per-player per-match stats

| Field | Source | S3 archive | Extractor | DB target |
|---|---|---|---|---|
| All 59 fields (tries, tackles, run metres, kicks, etc.) | nrl.com match-centre `stats.players.{homeTeam,awayTeam}[]` | `scout/nrlcom/match-centre/*` | `extract_player_match_stats` | `player_match_stats` (migration 056 — has all 59 columns) |
| `nrlcom_player_id` | match-centre `stats.players[*].playerId` | same | extractor | `player_match_stats.nrlcom_player_id` |
| `person_id` (FK) | Resolved via `people.nrlcom_player_id = nrlcom_player_id` | — | extractor | `player_match_stats.person_id` |
| `raw_payload` | Full per-player block (forensic capture) | same | extractor | `player_match_stats.raw_payload` (JSONB) |

### Match timeline (play-by-play)

| Field | Source | S3 archive | Extractor | DB target |
|---|---|---|---|---|
| `event_type` | match-centre `timeline[].type` (Try, Goal, Penalty, KickBomb, etc.) | `scout/nrlcom/match-centre/*` | `extract_match_timeline` | `match_timeline.event_type` |
| `title`, `game_seconds`, `nrlcom_team_id` | match-centre `timeline[].title`, `.gameSeconds`, `.teamId` | same | extractor | `match_timeline.title`, `.game_seconds`, `.nrlcom_team_id` |
| `team_id` | Resolved via teams.nrlcom_team_id | same | extractor | `match_timeline.team_id` |
| `nrlcom_player_id`, `person_id` | match-centre `timeline[].playerId` (present on Try/Goal/Error/etc.) | same | extractor (JOIN people on nrlcom_player_id) | `match_timeline.nrlcom_player_id`, `.person_id` |
| `running_home_score`, `running_away_score` | match-centre `timeline[].homeScore`, `.awayScore` (present on scoring events) | same | extractor (after Tier 2 migration adds columns) | `match_timeline.running_home_score`, `.running_away_score` (future) |
| `raw_payload` | Full event dict | same | extractor | `match_timeline.raw_payload` (JSONB) |

### Match officials

| Field | Source | S3 archive | Extractor | DB target |
|---|---|---|---|---|
| `first_name`, `last_name`, `role` | match-centre `officials[].firstName/.lastName/.position` | match-centre | `extract_match_officials` | `match_officials.first_name`, `.last_name`, `.role` |
| `person_id` | Optional — `people.nrlcom_player_id = officials[].profileId` if person row exists | same | extractor | `match_officials.person_id` (nullable) |
| `raw_payload` | Full official dict | same | extractor | `match_officials.raw_payload` |

### Player rounds (SuperCoach overlay)

`player_rounds` is the SC scoring-breakdown table. Per [D11](drafts/scout-charter-expansion.draft.md), the SC scoring components (`base`/`attack`/`playmaking`/`power`/`negative`) only exist in nrlsupercoachstats.

| Field | Source | S3 archive | Extractor | DB target |
|---|---|---|---|---|
| Identity (`player_id`, `player_name`, `team`, `position`, `round`, `season`) | nrlsupercoachstats jqGrid row identity | `scout/nrlsupercoachstats/stats/{season}/round-{NN}.json` | `extract_player_rounds` (currently inline in `scout/supercoach_stats/routes.py`) | `player_rounds.player_id`, etc. |
| SC scoring breakdown + raw counts + percentages (50+ fields) | jqGrid extracted columns | same | extractor | `player_rounds.base`, `.attack`, `.playmaking`, `.power`, `.negative`, tries, tackles, etc. |
| `price`, `start_price`, `end_price`, `magic_number`, etc. | jqGrid Price/StartPrice/EndPrice/etc. | same | extractor | `player_rounds.price`, … |
| Lookahead overlay (SC.com.au): `opp1/opp2/opp3`, `ven1/ven2/ven3`, `ppts`, `owned`, `mvp_value`, `position_ranks` | SC `players-cf` `player_stats[]` | `scout/supercoach/classic/players-cf/*` | Future SC overlay extractor | `player_rounds.metadata_json.sc_lookahead` (after Tier 2 migration adds `metadata_json` to player_rounds) |
| `match_id` (FK) | Resolved via (team, season, round) → `matches` | — | extractor | `player_rounds.match_id` |

### Injuries (casualty ward)

| Field | Source | S3 archive | Extractor | DB target |
|---|---|---|---|---|
| `first_name`, `last_name`, `team`, `injury` (body part), `expected_return` | nrl.com casualty `casualties[].firstName/.lastName/.teamNickname/.injury/.expectedReturn` | `scout/nrlcom/casualty-ward/{comp}/{YYYYMMDD}.json` | `extract_injuries` | `injuries.first_name` (no — `people` JOIN), `.body_part` (from `injury` text), `.expected_return_round` (parse "Round 11" → 11), `.team_id`, `.player_id` |
| `player_id` | Resolved via name+team → `people` | — | extractor | `injuries.player_id` |
| `reported_at`, `resolved_at` | Diffing snapshots — first appearance = reported, first absence = resolved | same | extractor (state-machine over daily snapshots) | `injuries.reported_at`, `.resolved_at` |
| `source` | `"nrl.com/casualty-ward"` | — | extractor | `injuries.source` |

### Team standings (ladder)

| Field | Source | S3 archive | Extractor | DB target |
|---|---|---|---|---|
| `team_id`, `nrlcom_team_nickname` | nrl.com ladder `positions[].teamNickname` | `scout/nrlcom/ladder/{comp}/{season}/round-{NN}.json` | `extract_team_standings` | `team_standings.team_id` (via name lookup), `.nrlcom_team_nickname` |
| `ladder_position`, `movement` | `positions[]` order + `.movement` | same | extractor | `team_standings.ladder_position`, `.movement` |
| 22 metrics: `played`, `wins`, `lost`, `drawn`, `byes`, `points`, `points_for`, `points_against`, `points_difference`, `bonus_points`, `form`, `streak`, `home_record`, `away_record`, `day_record`, `night_record`, `average_winning_margin`, `average_losing_margin`, `close_games`, `golden_point`, `players_used`, `odds` | `positions[].stats.*` (dict with 22 keys) | same | extractor | `team_standings.*` (migration 059 has all 22 columns) |
| `raw_payload` | Full position dict | same | extractor | `team_standings.raw_payload` (JSONB) |

### Stat leaderboards

| Field | Source | S3 archive | Extractor | DB target |
|---|---|---|---|---|
| `scope` ('player' / 'team'), `category`, `subgroup`, `stat_title`, `stat_id` | nrl.com stats `playerStats[]` / `teamStats[]` (with `groups[].title`, `groups[].stats[]`) | `scout/nrlcom/stats/{comp}/{season}.json` | `extract_stat_leaderboards` | `stat_leaderboards.scope`, `.category`, `.subgroup`, `.stat_title`, `.stat_id` |
| `leader_position`, `leader_first_name`, `leader_last_name`, `leader_team_nickname`, `leader_value` | `stats[].leaders[]` array (top-25 per stat) | same | extractor | `stat_leaderboards.leader_*` |
| `person_id` (player scope) | Resolved via `people.nrlcom_player_id = leader.playerId` | same | extractor | `stat_leaderboards.person_id` |
| `team_id` (team scope) | Resolved via teams.nrlcom_team_id | same | extractor | `stat_leaderboards.team_id` |

### SC editorial claims (notes → wiki content)

This pipeline is **already shipped end-to-end** — no extractor needed. It runs inline in `scout/supercoach_roster/` and writes directly to DB.

| Field | Source | S3 archive | Code path | DB target |
|---|---|---|---|---|
| `quoted_text` | SC `notes[].note` | `scout/supercoach/classic/players-cf/*` | `scout/supercoach_roster/notes_extractor.py` (shipped) | `quotes.quoted_text` |
| `speaker_person_id` | Synthetic SC Editorial entity (UUID `aaaaaaaa-...-000000000001`) | seeded via migration 061 | same | `quotes.speaker_person_id` |
| `said_at_reference` | SC `notes[].created_on` (ISO timestamp) | same | same | `quotes.said_at_reference` |
| `claim_type` | Keyword heuristic over note text | same | `notes_extractor.classify_claim_type()` | `claims.claim_type` |
| `claim_text` | SC note prose | same | same | `claims.claim_text` |
| `payload_json` | `{source: 'supercoach-editorial-notes', sc_player_id, created_on}` | same | same | `claims.payload_json` |
| Subject person | Resolved via `people.supercoach_id = note.player_id` | same | same | `claim_associations.person_id` (role='subject') |

**Output as of 2026-05-12:** 846 claims, 206 distinct players covered.

### SuperCoach game settings

| Field | Source | S3 archive | Extractor | DB target |
|---|---|---|---|---|
| All settings (competition/content/game/system) | SC `/settings` JSON envelope (4 top-level keys, ~100 leaf fields) | `scout/supercoach/{mode}/settings/{season}/{YYYYMMDD}.json` | Inline in `scout/supercoach_settings/routes.py` (shipped) | `sc_settings.payload` (JSONB — whole payload stored unsliced) |
| `season`, `mode` | Captured per call | same | same | `sc_settings.season`, `.mode` (idempotent on `(season, captured_date, mode)`) |

---

## Reverse view — per-DB-table provenance

For each DB table, which S3 archives populate it, and via which code path.

| DB table | S3 archive(s) | Extractor | Status | Trust source per [D11](drafts/scout-charter-expansion.draft.md) |
|---|---|---|---|---|
| `people` | `scout/supercoach/classic/players-cf/*` (primary) + `scout/nrlcom/match-centre/*` (coaches + nrlcom IDs) + `scout/nrlsupercoachstats/stats/*` (historical union, pending) | `scout/supercoach_roster/` + `scripts/data/populate/phase_identity.py` (nrlcom IDs + coaches) ⊕ future `extract_people_history` (for the 735 historical-only players) | ✅ shipped (593 = 572 SC + 21 coaches; 516 have nrlcom_player_id) / 🟡 history pending | SC for SC-eligible roster; nrl.com for biographical (DOB, image) + coaches |
| `player_attributes` | SC roster + nrl.com profile enrichment | `scout/supercoach_roster/` (SCD-2 close/open on diff) | ✅ shipped | SC for team/position; nrl.com for height/weight/contract |
| `people_roles` | SC roster (player), match-centre coaches (coach), Analyst diarisation (advisor) | `scout/supercoach_roster/` (player); coach role is set via `people.metadata_json.role_class='coach'` from phase_identity (a proper `people_roles` row per coach tenure is a follow-up) | ✅ player roles shipped; ⚠️ coach roles tracked via metadata only; advisor pending | per role-class |
| `teams` | Seeded once; `scout/supercoach/classic/teams/*` for SC ID enrichment; `scout/nrlcom/match-centre/*` for nrl.com ID | Seed + `scout/supercoach_teams/` + `scripts/data/populate/phase_identity.py` (nrl.com IDs) | ✅ shipped (17/19 NRL teams have nrlcom_team_id) | Seed for identity; nrl.com IDs from match-centre |
| `venues` | Seeded; future enrichment from match-centre venue strings | Seed | ✅ seeded | Manual; nrl.com text is informational |
| `matches` | `scout/nrlcom/match-centre/*` (primary) + `scout/nrlcom/draw/*` (round metadata, kickoff_at) | `scripts/data/populate/phase_matches.py` | ✅ shipped (408 rows 2025-2026, historical backfill in progress) | nrl.com canonical |
| `match_team_lists` | `scout/nrlcom/match-centre/*` (positionGroups + players[] + coaches[]) | `scripts/data/populate/phase_team_lists.py` | ✅ shipped (10,447 rows incl. 584 coaches) | nrl.com canonical |
| `player_match_stats` (migration 056) | `scout/nrlcom/match-centre/*` (stats.players.{homeTeam,awayTeam}[]) | `scripts/data/populate/phase_stats.py` | ✅ shipped (10,384 rows × 59 fields) | nrl.com canonical |
| `match_timeline` (migration 057) | `scout/nrlcom/match-centre/*` (timeline[]) | `scripts/data/populate/phase_timeline.py` | ✅ shipped (31,563 events, running scores) | nrl.com canonical |
| `match_officials` (migration 058) | `scout/nrlcom/match-centre/*` (officials[]) | `scripts/data/populate/phase_timeline.py` (combined w/ timeline) | ✅ shipped (948 rows) | nrl.com canonical |
| `team_standings` (migration 059) | `scout/nrlcom/ladder/*` | `scripts/data/populate/phase_aux.py` | ✅ shipped (481 rows historical ladders) | nrl.com canonical |
| `stat_leaderboards` (migration 060) | `scout/nrlcom/stats/*` | `scripts/data/populate/phase_aux.py` | ✅ shipped (4,594 rows 2013-2025) | nrl.com canonical |
| `injuries` | `scout/nrlcom/casualty-ward/*` (daily diff) | `scripts/data/populate/phase_aux.py` (state-machine over snapshots) | ✅ shipped (98 active) | nrl.com canonical |
| `rounds` | `scout/nrlcom/draw/*` (round-level metadata) | `scripts/data/populate/phase_rounds.py` | ✅ shipped (756 rounds 1908-2026) | nrl.com canonical |
| `player_rounds` | `scout/nrlsupercoachstats/stats/*` (primary — SC scoring breakdown) + `scout/supercoach/classic/players-cf/*.player_stats[]` (SC lookahead overlay) | `scout/supercoach_stats/` (shipped, primary path) + future SC overlay extractor | ✅ primary shipped; 🟡 SC overlay pending | nrlsupercoachstats for scoring breakdown (only source); SC for lookahead/projection |
| `sc_settings` (migration 055) | `scout/supercoach/{mode}/settings/*` | Inline in `scout/supercoach_settings/` | ✅ shipped | SC (only source) |
| `quotes` | `scout/supercoach/classic/players-cf/*` (notes[]) — and future Analyst transcript extraction | `scout/supercoach_roster/notes_extractor.py` (shipped) + future Analyst pipeline | ✅ SC notes shipped (846 rows) | Analyst per-source attribution; synthetic SC Editorial for notes |
| `claims` | Same as `quotes` (1:1 from notes) — and future Analyst extraction | same | ✅ SC notes shipped (846 claims) | per-source |
| `claim_associations` | Same (links claims to subjects) | same | ✅ shipped | — |
| `agent_runs`, `agent_events` | Every Scout pipeline writes one `agent_runs` row per invocation | All Scout pipelines | ✅ shipped | — |

---

## Identity-resolution cross-reference

The three external sources don't share player IDs. The `people` table is the merge point.

```
   SC players-cf            nrl.com match-centre           nrlsupercoachstats
   ─────────────            ──────────────────             ──────────────────
        │                          │                              │
        │ id (small int)           │ playerId (BIGINT)            │ name+team hashed
        │ e.g. 282                 │ e.g. 100012669               │ → integer key
        ▼                          ▼                              ▼
   ┌──────────────────────────────────────────────────────────────┐
   │                       people                                  │
   │   person_id (UUID)                                            │
   │   supercoach_id    BIGINT  ◀── SC roster pipeline writes     │
   │   nrlcom_player_id BIGINT  ◀── future extractor writes       │
   │   canonical_name, slug                                        │
   └──────────────────────────────────────────────────────────────┘
        ▲
        │ matched via:
        │   - exact: supercoach_id, nrlcom_player_id
        │   - fuzzy: canonical_name + team (for nrlsupercoachstats hash → people row)
        │
   ┌──────────────────────────────────────────────────────────────┐
   │   extractors (Scout downstream)                               │
   │     player_match_stats → JOIN people ON nrlcom_player_id     │
   │     player_rounds      → name+team match to people           │
   │     claims/quotes      → JOIN people ON supercoach_id (notes)│
   └──────────────────────────────────────────────────────────────┘
```

**`nrlcom_player_id` is the missing piece** — added in migration 062. Until populated, match-centre extractors fall back to name matching (slower, fragile). The future `extract_nrlcom_identity` job walks `scout/nrlcom/players-roster/*` and `scout/nrlcom/match-centre/*` to populate `people.nrlcom_player_id` by name+team match against existing rows.

---

## Coverage map (what's reachable vs what's in DB today)

| Era | Source layer (S3) | Extracted to DB |
|---|---|---|
| **1908–1989** | Fixtures only (nrl.com draw — 3,213 archives) | rounds + matches identity (pending extractor) |
| **1990–1998** | Fixtures + thin match-centre (no lineups in match-centre payloads) | rounds + match identity (pending) |
| **1999–2017** | Full match-centre (lineups, 58-field stats, timeline) + fixtures | Everything from 2 yrs forward of nrlsupercoachstats start (pending) |
| **2018–2024** | Full match-centre + nrlsupercoachstats SC scoring (215 successful captures) | player_rounds (would land once extractor runs) + match details (pending) |
| **2025** | All of above + SC `players-cf` (586 players, full season) | Same as 2018-2024 |
| **2026 (current)** | All of above + daily snapshots of casualty ward, ladder, etc. | SC roster (550) + 206 players with editorial claims + 17 teams + sc_settings ✅ |

---

## What's downstream (Layer 4 — the app)

Once extractors populate the DB tables above, the app surfaces them:

| App surface | Reads from |
|---|---|
| Wiki player page `## Current Form` | `player_rounds` joined by `people.person_id` |
| Wiki player page `## Recent Match` | `match_team_lists` ⊕ `player_match_stats` ⊕ `match_timeline` for the player |
| Wiki player page `## Expert Opinions` | `claims` ⊕ `quotes` ⊕ `claim_associations` |
| Wiki team page `## Recent Results` | `matches` filtered by `home_team_id`/`away_team_id` |
| Wiki team page `## Ladder Position` | `team_standings` for the current round |
| Wiki team page `## Key Players` | `stat_leaderboards` filtered by `team_id` |
| Wiki round page `## Team Lists` | `match_team_lists` filtered by `match.round` |
| Wiki round page `## Results` | `matches` + `match_timeline` for the round |
| Wiki round page `## Casualty Ward` | `injuries` active at the round date |
| Ledger / Bookkeeper | `claims` (predictions) ⊕ outcomes-resolved-from `matches`/`player_rounds` |

The app reads from the DB. **The DB is fully re-derivable from S3 archives** — any time, no upstream re-fetch needed.

---

## Maintenance

Authoritative per-table lineage now lives in [`docs/operations/data-lineage/`](../operations/data-lineage/README.md). The per-domain tables in this document are a frozen snapshot from 2026-05-13 — **don't update them in place**. Update the per-table file in the new folder instead.

When schema or pipelines change:
1. Update the per-table file in `docs/operations/data-lineage/<table>.md`
2. Update [`docs/operations/data-catalogue/<table>.md`](../operations/data-catalogue/README.md) if a column was added/removed
3. Regenerate the affected [`docs/operations/data-sources/<source>/<pipeline>.md`](../operations/data-sources/README.md) profile if upstream JSON shape changed
4. Field-name churn is captured by D8 drift fixtures — drift tests catch upstream shape changes before they silently mis-map

This document only changes when the **conceptual** model changes (L1/L2/L3 boundaries, identity-resolution approach, downstream surface map).

---

## Related

- [`docs/pages/wiki/data-feeds.md`](../pages/wiki/data-feeds.md) — wiki-centric reverse view
- [`docs/agents/crew/scout.md`](../agents/crew/scout.md) — pipeline inventory + hand-off contract
- [`docs/architecture/04-information-architecture.md`](04-information-architecture.md) — domain model
- [`docs/architecture/drafts/scout-charter-expansion.draft.md`](drafts/scout-charter-expansion.draft.md) — locked D1–D13 governing the lineage
- Per-pipeline READMEs in `services/api/app/scout/{pipeline}/README.md`
