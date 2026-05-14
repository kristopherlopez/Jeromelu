---
tags: [area/operations, data-catalogue]
---

# matches

[← Data Catalogue](README.md) · [Lineage](../data-lineage/matches.md) · Layer 2 — Structured world

Fixture / result spine — one row per game across all grades (NRL, NRLW,
NSW Cup, QLD Cup, junior pathway). Real-world side of the model;
[player_rounds](player_rounds.md) is the SuperCoach overlay that joins via `match_id`.

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
| attendance | int | yes | | NULL when nrl.com reports 0 (sentinel for unknown) (mig 063) |
| ground_conditions | text | yes | | e.g. `Fine`, `Wet` (mig 063) |
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

Populated by the daily fixture-sync against the NRL.com draw API (see [docs/agents/system/scraper.md](../../agents/system/scraper.md)).

**Bye rows:** `status='bye'` indicates a bye for `home_team_id` (the column is semantically overloaded for byes — it just means "the team in question," not literally "home team"). `away_team_id`, `kickoff_at`, scores, weather, broadcast are all NULL. Match queries that don't want byes filter `WHERE status<>'bye'` or `WHERE away_team_id IS NOT NULL`.
