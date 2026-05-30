---
tags: [area/operations, data-lineage]
---

# Lineage: injuries

[Schema: data-catalogue/injuries.md](../data-catalogue/injuries.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| nrl.com / casualty-ward | [data-sources/nrlcom/casualty-ward.md](../data-sources/nrlcom/casualty-ward.md) | **Primary** — daily snapshot |

Schema also allows `source='zerotackle'`, `'nrl_physio_twitter'`, `'manual'`, but no extractor populates these today.

## Extractor

`scripts/data/populate/phase_aux.py` — `populate_injuries()` runs a state machine over chronologically-sorted casualty snapshots. For each daily snapshot under `miner/nrlcom/casualty-ward/{competition}/{YYYYMMDD}.json`:

1. For each casualty in today's payload: if no open injury exists for `(player_id, team_id, description)`, INSERT a new row. If one exists, UPDATE its `expected_return_round` and `metadata_json.last_seen_snapshot`.
2. For each previously-open injury whose `(name, team_nick)` key is **not** in today's snapshot: SET `resolved_at = snap_date`.

Resolution:
- `team_id`: lookup on `teams` by lower-cased nickname/slug/aliases
- `player_id`: lookup on `people` by `(canonical_name.lower(), team_nickname.lower())`, falls back to name-only

## Field mapping

| DB column | Source | Source field | Notes |
|---|---|---|---|
| `injury_id` | derived | — | UUID, DB-side default |
| `player_id` | resolved | `$.casualties[*].firstName + lastName` via people lookup | NULL if no person match |
| `team_id` | resolved | `$.casualties[*].teamNickname` via team lookup | |
| `status` | derived | `$.casualties[*].expectedReturn` text → `_bucket_status()` | Maps "indefinite", "Round N" (gap-based: `1_week`, `2_4_weeks`, `4_8_weeks`), "training", "test", "next season" → enum |
| `body_part` | casualty-ward | `$.casualties[*].injury` | Free-text from source |
| `mechanism` | not extracted | — | Future enrichment |
| `description` | casualty-ward | `firstName + ' ' + lastName` | Used as the `(player, team, description)` natural key for state-machine matching |
| `expected_return_round` | derived | regex `Round\s+(\d+)` on `expectedReturn` | NULL if not parseable |
| `expected_return_date` | not extracted | — | |
| `severity` | not extracted | — | Future enrichment |
| `reported_at` | S3 key | `casualty-ward/.../{YYYYMMDD}.json` | Snapshot date, midnight UTC |
| `resolved_at` | derived | snap_date when player drops out of casualty list | |
| `source` | constant | `'nrl.com/casualty-ward'` | |
| `source_url` | casualty-ward | `$.casualties[*].url` | |
| `metadata_json` | mixed | `expected_return_text`, `first_snapshot`, `last_seen_snapshot`, `team_nickname` | |
| `created_at` | derived | — | DB default `now()` |

## State-machine notes

- Append-on-change: not every snapshot writes a new row. Existing open injuries get `metadata_json.last_seen_snapshot` updated in place.
- Resolution detection is **whole-snapshot diff**: if a player drops out of today's casualty list, their open injury is closed with `resolved_at = today's snap_date`. No separate "cleared" status comes from upstream.
- Status bucketing depends on the current round (`MAX(matches.round)` for the season at snap time) — gap of 1 week → `1_week`, 2-4 → `2_4_weeks`, 4+ → `4_8_weeks`.

## Coverage

99 active (open) casualty-ward injuries as of the 2026-05-28 seed (130 total rows; 31 closed by the state machine using the prior 2026-05-12 snapshot). Daily cron (18:30 UTC) builds the append-on-change timeline going forward; once it accumulates, INSERTs are rare — most days just stamp `metadata_json.last_seen_snapshot` on existing open rows. Team-id resolution rate ~93%.
