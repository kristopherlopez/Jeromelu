---
tags: [area/operations, data-catalogue]
---

# stat_leaderboards

[← Data Catalogue](README.md) · [Lineage](../data-lineage/stat_leaderboards.md) · Layer 2 — Structured world

Pre-computed top-25 leaderboards from nrl.com `/stats/data`. One row per (category, subgroup, stat, season, position-in-leaders). The nrl.com response groups `playerStats[].groups[].stats[].leaders[]` and a parallel `teamStats[]`; flattened here into one wide table. Added in mig 060.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| competition | int | no | | 111 for NRL etc. |
| season | int | no | | |
| scope | text | no | | `player` or `team` |
| category | text | no | | `Scoring`, `Attack`, `Passing`, ... |
| subgroup | text | no | | `Points`, `Tries`, `Goals`, ... |
| stat_id | int | yes | | nrl.com internal stat id |
| stat_title | text | no | | `Total Points`, `Tries per Game`, ... |
| leader_position | int | no | | 1..25 |
| leader_first_name | text | yes | | |
| leader_last_name | text | yes | | |
| leader_team_nickname | text | yes | | |
| leader_value | float | yes | | The metric value |
| person_id | UUID | yes | | FK → people; resolved by extractor for `scope='player'` |
| team_id | UUID | yes | | FK → teams; resolved for `scope='team'` |
| raw_payload | jsonb | no | | Full leader block |
| s3_archive_key | text | yes | | |
| captured_at | timestamptz | no | now() | Refreshed each fetch |
| created_at | timestamptz | no | now() | |

**Unique:** `(competition, season, scope, category, subgroup, stat_title, leader_position)` — same season + scope + stat + position UPSERT (re-fetch updates value if nrl.com revised post-game)
**Check:** `scope IN ('player', 'team')`
**Indexes:** season, person_id (partial: WHERE NOT NULL), team_id (partial: WHERE NOT NULL)
**FK:** person_id → people; team_id → teams
