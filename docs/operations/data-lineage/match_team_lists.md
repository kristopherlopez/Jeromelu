---
tags: [area/operations, data-lineage]
---

# Lineage: match_team_lists

[Schema: data-catalogue/match_team_lists.md](../data-catalogue/match_team_lists.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| nrl.com / match-centre | [data-sources/nrlcom/match-centre.md](../data-sources/nrlcom/match-centre.md) | **Primary** — both players and coaches |

## Extractor

`scripts/data/populate/phase_team_lists.py` — `populate_team_lists()`. Two row classes per match:

1. **Players** — one row per (match, team, player) from `$.{home,away}Team.players[*]`
2. **Coaches** — one row per (match, team, coach) from `$.{home,away}Team.coaches[*]` with `jersey_number=NULL` and `named_position` in `{Coach, Assistant Coach}`. Coach `profileId` is stored on `people.nrlcom_player_id` (same identity space upstream).

Resolution:
- `match_id`: lookup on `matches.external_match_id`
- `team_id`: lookup on `teams.nrlcom_team_id`
- `player_id` (for players): lookup on `people.nrlcom_player_id`
- `player_id` (for coaches): same lookup, with auto-INSERT into `people` if missing (`_ensure_coach_person`)

## Field mapping

| DB column | Source | Source field | Notes |
|---|---|---|---|
| `list_id` | derived | — | UUID, DB-side default |
| `match_id` | resolved | via `matches.external_match_id` | Skipped if no match row |
| `team_id` | resolved | `$.{side}.teamId` via `teams.nrlcom_team_id` | Skipped if no team |
| `player_id` | resolved | `$.{side}.players[*].playerId` (or `coaches[*].profileId`) via `people.nrlcom_player_id` | Players: skipped if no person; coaches: auto-insert |
| `jersey_number` | match-centre | `$.{side}.players[*].number` | NULL for coaches |
| `named_position` | match-centre | `$.{side}.players[*].position` (or coach `position` field) | Coaches: `Coach`, `Assistant Coach`, etc. |
| `sc_position` | not extracted | — | Future cross-ref to SC eligibility |
| `is_captain` | match-centre | `$.{side}.captainPlayerId == player.playerId` | False for coaches |
| `list_version` | constant | `1` | Monotonically increasing per (match, team) when lineup-snapshot versions are modelled separately; today only post-match v1 written |
| `status` | constant | `'named'` | |
| `announced_at` | not extracted | — | Future: derive from match-centre `updated` timestamp |
| `source` | constant | `'nrl_com'` | |
| `metadata_json` | not extracted | — | Empty |
| `created_at` | derived | — | DB default `now()` |

## Idempotency

No DB unique constraint on `(match_id, team_id, player_id, list_version)` — the schema supports multiple list versions. The extractor pre-checks existence with `SELECT 1` before INSERT to avoid duplicates on re-runs.

For coaches, the existence check also matches on `named_position` since the same person can hold both `Coach` and `Assistant Coach` roles across matches.

## Notes

- Late-change versions (Tue/Wed/Thu/Late) require Tier-2 modelling (multiple `list_version` rows per match-team); not built today.
- ~10,447 rows including 584 coach rows as of recent backfill.
