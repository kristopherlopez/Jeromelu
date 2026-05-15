---
tags: [area/operations, data-lineage]
---

# Lineage: team_standings

[Schema: data-catalogue/team_standings.md](../data-catalogue/team_standings.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| nrl.com / ladder | [data-sources/nrlcom/ladder.md](../data-sources/nrlcom/ladder.md) | **Primary** — one row per team per round per season |

## Extractor

`scripts/data/populate/phase_aux.py` — `populate_team_standings()`. Walks `scout/nrlcom/ladder/{competition}/...`, idempotent UPSERT on `(nrlcom_team_nickname, competition, season, round)`. ~481 rows shipped.

## Field mapping

| DB column | Source | Source field | Notes |
|---|---|---|---|
| `id` | derived | — | UUID |
| `team_id` | resolved | via `teams.slug`/`short_name`/`aliases` (lower-cased) | NULL if no match |
| `nrlcom_team_nickname` | ladder | `$.positions[*].teamNickname` | Used for lookup; part of unique key |
| `competition` | S3 key | `scout/.../{competition}/...` | |
| `season` | S3 key | `scout/.../{season}/round-{NN}.json` | |
| `round` | S3 key | Same | |
| `ladder_position` | ladder | `$.positions[*].position` (or enumerate index) | |
| `movement` | ladder | `$.positions[*].movement` | `up`, `down`, `none` |
| `played`, `wins`, `lost`, `drawn`, `byes`, `points`, `points_for`, `points_against`, `points_difference`, `bonus_points` | ladder | `$.positions[*].stats.<key>` | Direct mapping (note keys have spaces upstream: `"points for"` etc.) |
| `form`, `streak`, `home_record`, `away_record`, `day_record`, `night_record` | ladder | Same | Free-text |
| `average_winning_margin`, `average_losing_margin`, `close_games`, `golden_point`, `players_used`, `odds` | ladder | Same | |
| `raw_payload` | ladder | full position payload | |
| `s3_archive_key` | derived | the source key | |
| `created_at`, `updated_at` | derived | DB defaults | |

## UPSERT semantics

On conflict, all stat fields overwrite. `team_id` uses `COALESCE(EXCLUDED, team_standings)` — won't clobber a known resolution with NULL on a re-extract before the team is mapped.

## Notes

- See migration 059.
