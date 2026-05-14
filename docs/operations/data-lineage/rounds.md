---
tags: [area/operations, data-lineage]
---

# Lineage: rounds

[Schema: data-catalogue/rounds.md](../data-catalogue/rounds.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| nrl.com / draw | [data-sources/nrlcom/draw.md](../data-sources/nrlcom/draw.md) | Primary — one draw archive per (competition, season, round) |

## Extractor

`scripts/data/populate/phase_rounds.py` — `populate_rounds()` walks `scout/nrlcom/draw/{competition}/{season}/round-{NN}.json`, idempotent UPSERT on `(season, round_number)`.

## Field mapping

| DB column | Source | Source field | Notes |
|---|---|---|---|
| `round_id` | derived | — | UUID, DB-side default |
| `season` | S3 key | `scout/.../{season}/...` | Parsed from key path |
| `round_number` | S3 key | `scout/.../round-{NN}.json` | Parsed from key path |
| `round_label` | draw | `$.filterRounds[*].name` where `value == round_number` | Falls back to `"Round {N}"` if no match |
| `starts_at` | draw | `MIN($.fixtures[*].clock.kickOffTimeLong)` | |
| `ends_at` | draw | `MAX($.fixtures[*].clock.kickOffTimeLong)` | |
| `is_magic_round` | not extracted | — | Always false; future enhancement |
| `is_rep_weekend` | not extracted | — | Always false |
| `is_finals` | derived | `round_label` contains "Final", "Qualifying", or "Elimination" | |
| `metadata_json` | not extracted | — | Empty `{}` |

## UPSERT semantics

On conflict, all fields except identity overwrite: `round_label`, `starts_at`, `ends_at`, `is_finals`. Idempotent against re-runs and round-label corrections.

## Coverage

756 rounds across 1908-2026 are populated for competition 111 (NRL). Other competitions (NRLW, NSW Cup, QLD Cup) would need parallel extractor calls with their respective comp IDs; no data today.
