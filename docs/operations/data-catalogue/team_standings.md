---
tags: [area/operations, data-catalogue]
---

# team_standings

[← Data Catalogue](README.md) · [Lineage](../data-lineage/team_standings.md) · Layer 2 — Structured world

Per-round team-table positions + 22 per-team metrics from nrl.com `/ladder/data`. One row per (team, season, round); same-round re-runs UPSERT. Added in mig 059.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| team_id | UUID | yes | | FK → teams; nullable when nickname doesn't resolve |
| nrlcom_team_nickname | text | no | | `Panthers`, `Broncos` etc. — used for lookup if `team_id` unresolved |
| competition | int | no | | 111 for NRL, 161 for NRLW etc. |
| season | int | no | | |
| round | int | no | | |
| ladder_position | int | yes | | 1..17 |
| movement | text | yes | | `up`, `down`, `none` |
| played | int | yes | | |
| wins | int | yes | | |
| lost | int | yes | | |
| drawn | int | yes | | |
| byes | int | yes | | |
| points | int | yes | | |
| points_for | int | yes | | |
| points_against | int | yes | | |
| points_difference | int | yes | | |
| bonus_points | int | yes | | |
| form | text | yes | | Last-N results string |
| streak | text | yes | | |
| home_record | text | yes | | |
| away_record | text | yes | | |
| day_record | text | yes | | |
| night_record | text | yes | | |
| average_winning_margin | float | yes | | |
| average_losing_margin | float | yes | | |
| close_games | int | yes | | |
| golden_point | int | yes | | |
| players_used | int | yes | | |
| odds | text | yes | | |
| raw_payload | jsonb | no | | Full ladder position payload |
| s3_archive_key | text | yes | | |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | |

**Unique:** `(nrlcom_team_nickname, competition, season, round)`
**Indexes:** team_id, (season, round)
**FK:** team_id → teams
