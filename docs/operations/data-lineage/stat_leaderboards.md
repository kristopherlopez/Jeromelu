---
tags: [area/operations, data-lineage]
---

# Lineage: stat_leaderboards

[Schema: data-catalogue/stat_leaderboards.md](../data-catalogue/stat_leaderboards.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| nrl.com / stats | [data-sources/nrlcom/stats.md](../data-sources/nrlcom/stats.md) | **Primary** — pre-computed top-25 leaderboards per stat |

## Extractor

`scripts/data/populate/phase_aux.py` — `populate_stat_leaderboards()`. Walks `scout/nrlcom/stats/{competition}/...`, flattens nested `playerStats[].groups[].stats[].leaders[]` (and parallel `teamStats[]`) into one wide table. Idempotent UPSERT on `(competition, season, scope, category, subgroup, stat_title, leader_position)`. ~4,594 rows shipped (2013-2025).

## Field mapping

| DB column | Source | Source field | Notes |
|---|---|---|---|
| `id` | derived | — | UUID |
| `competition` | S3 key | `scout/.../{competition}/...` | |
| `season` | S3 key | `scout/.../{season}.json` | |
| `scope` | extractor | `'player'` or `'team'` | Branch on `playerStats` vs `teamStats` block |
| `category` | stats | `<scope>Stats[*].title` | `Scoring`, `Attack`, `Passing`, ... |
| `subgroup` | stats | `<scope>Stats[*].groups[*].title` | `Points`, `Tries`, `Goals`, ... |
| `stat_id` | stats | `groups[*].statId` | Internal nrl.com stat id |
| `stat_title` | stats | `groups[*].title` | Mirrors `subgroup` today |
| `leader_position` | extractor | enumerate over `leaders[*]` (1-based) | |
| `leader_first_name`, `leader_last_name` | stats | `leaders[*].firstName`, `lastName` | |
| `leader_team_nickname` | stats | `leaders[*].teamNickName` (or `teamName` fallback) | |
| `leader_value` | stats | `leaders[*].value` (cast to float) | NULL on parse failure |
| `person_id` | resolved | via `people.nrlcom_player_id` | Only set for `scope='player'` when `leaders[*].playerId` resolves |
| `team_id` | resolved | via team-nickname lookup | |
| `raw_payload` | stats | full leader payload | |
| `s3_archive_key` | derived | the source key | |
| `captured_at` | derived | DB default `now()` on each refresh | |
| `created_at` | derived | DB default `now()` | |

## UPSERT semantics

On conflict, leader name/team/value refresh in place (re-fetch picks up nrl.com's revisions). `person_id` and `team_id` use `COALESCE(EXCLUDED, stat_leaderboards)` — won't clobber a known resolution with NULL.

## Notes

- See migration 060.
- `scope='team'` rows leave `person_id` NULL by design.
