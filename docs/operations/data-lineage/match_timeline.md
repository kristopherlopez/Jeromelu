---
tags: [area/operations, data-lineage]
---

# Lineage: match_timeline

[Schema: data-catalogue/match_timeline.md](../data-catalogue/match_timeline.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| nrl.com / match-centre | [data-sources/nrlcom/match-centre.md](../data-sources/nrlcom/match-centre.md) | **Primary** — `$.timeline[*]` events |

## Extractor

`scripts/data/populate/phase_timeline.py` — `populate_timeline_and_officials()` (combined writer with [match_officials](match_officials.md)). One pass over match-centre archives writes both. Idempotent UPSERT on `(nrlcom_match_id, sequence)`. ~31,563 events shipped.

## Field mapping

| DB column | Source | Source field | Notes |
|---|---|---|---|
| `id` | derived | — | UUID |
| `match_id` | resolved | via `matches.external_match_id` | NULL if no match row |
| `nrlcom_match_id` | match-centre | `$.matchId` | Idempotency key part 1 |
| `sequence` | extractor | enumerate index over `$.timeline[*]` | 0..N per match |
| `event_type` | match-centre | `$.timeline[*].type` | `Try`, `Goal`, `SetRestart`, `GameTime`, `KickBomb`, ... (~19 distinct values per source profile) |
| `title` | match-centre | `$.timeline[*].title` | `KICK OFF`, `TRY!`, etc. (~49 distinct titles) |
| `game_seconds` | match-centre | `$.timeline[*].gameSeconds` | |
| `nrlcom_team_id` | match-centre | `$.timeline[*].teamId` | 0 for neutral game-state events |
| `team_id` | resolved | via `teams.nrlcom_team_id` | |
| `nrlcom_player_id` | match-centre | `$.timeline[*].playerId` | Present for events that reference a player |
| `person_id` | resolved | via `people.nrlcom_player_id` | |
| `running_home_score` | match-centre | `$.timeline[*].homeScore` | Score at the time of this event (mig 064) |
| `running_away_score` | match-centre | `$.timeline[*].awayScore` | Same |
| `raw_payload` | match-centre | the whole event payload | |
| `s3_archive_key` | derived | the source key | |
| `created_at` | derived | DB default `now()` | |

## UPSERT semantics

On conflict (`nrlcom_match_id`, `sequence`), all event fields overwrite. Sequence is regenerated on every run by enumerating `$.timeline[*]` — re-runs are deterministic.

## Notes

- See migration 057 (table) and 064 (running scores).
- Officials are extracted in the same pass — see [match_officials](match_officials.md).
