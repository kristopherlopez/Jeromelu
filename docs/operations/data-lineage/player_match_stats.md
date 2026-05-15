---
tags: [area/operations, data-lineage]
---

# Lineage: player_match_stats

[Schema: data-catalogue/player_match_stats.md](../data-catalogue/player_match_stats.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| nrl.com / match-centre | [data-sources/nrlcom/match-centre.md](../data-sources/nrlcom/match-centre.md) | **Primary** — per-player stat block |

## Extractor

`scripts/data/populate/phase_stats.py` — `populate_player_match_stats()` walks `scout/nrlcom/match-centre/{competition}/...`, idempotent UPSERT on `(nrlcom_match_id, nrlcom_player_id)`. ~10,384 rows × 59 fields shipped.

Resolution:
- `match_id`: lookup on `matches.external_match_id`
- `team_id`: lookup on `teams.nrlcom_team_id` (from per-team roster meta in match-centre)
- `person_id`: lookup on `people.nrlcom_player_id`
- `jersey_number`, `position`, `is_on_field`: pulled from `$.{home,away}Team.players[*]` (joined back by `playerId`)
- All ~58 stat fields: from `$.stats.players.{home,away}Team[*]` mapped via `_FIELD_MAP` (camelCase → snake_case)

## Field mapping

| DB column group | Source | Source field | Notes |
|---|---|---|---|
| `id` | derived | — | UUID |
| `match_id` | resolved | via `matches.external_match_id` | NULL if no match row |
| `nrlcom_match_id` | match-centre | `$.matchId` | Idempotency key part 1 |
| `nrlcom_player_id` | match-centre | `$.stats.players.{side}[*].playerId` | Idempotency key part 2 |
| `person_id` | resolved | via `people.nrlcom_player_id` | NULL if not yet resolved |
| `team_id` | resolved | via `teams.nrlcom_team_id` | |
| `nrlcom_team_id` | match-centre | `$.{side}.teamId` | |
| `is_home` | derived | side == `homeTeam` | |
| `jersey_number` | match-centre | `$.{side}.players[*].number` | Joined to stats by playerId |
| `position` | match-centre | `$.{side}.players[*].position` | Same |
| `is_on_field` | match-centre | `$.{side}.players[*].isOnField` | Same |
| ~58 stat fields | match-centre | `$.stats.players.{side}[*].<camelCase>` | Mapped via `phase_stats.py:_FIELD_MAP` |
| `raw_payload` | match-centre | the whole per-player block | Forensic capture so future-discovered columns can be derived |
| `s3_archive_key` | derived | the source key | |
| `created_at`, `updated_at` | derived | DB defaults | |

## UPSERT semantics

On conflict, every column refreshes (no COALESCE). Re-runs are deterministic.

## Notes

- D8 strict drift: every upstream camelCase field is modelled; if upstream adds/renames, the strict Pydantic extractor raises rather than silently dropping.
- See migration 056.
