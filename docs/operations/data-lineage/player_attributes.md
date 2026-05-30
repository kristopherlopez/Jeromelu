---
tags: [area/operations, data-lineage]
---

# Lineage: player_attributes

[Schema: data-catalogue/player_attributes.md](../data-catalogue/player_attributes.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| supercoach / classic-players-cf | [data-sources/supercoach/classic-players-cf.md](../data-sources/supercoach/classic-players-cf.md) | **Primary writer for SC-eligible players** — owns `is_current` rows for current SC roster |
| nrl.com / match-centre (via `match_team_lists`) | [data-sources/nrlcom/match-centre.md](../data-sources/nrlcom/match-centre.md) | Reconstructs historical tenure windows for non-SC players |

## Extractors

- `services/api/app/miner/supercoach_roster/` — writes SC-eligible player rows with `source='supercoach'`
- `scripts/data/populate/phase_attributes.py` — `populate_player_attributes()` reads `match_team_lists` chronologically, groups consecutive same-team appearances into tenure windows, UPSERTs with `source='nrlcom/match-centre'`

## Field mapping

| DB column | Source | Source field | Notes |
|---|---|---|---|
| `id` | derived | — | UUID, DB-side default |
| `person_id` | resolved | — | FK to people |
| `team_id` | match_team_lists | `mtl.team_id` | Same team across the contiguous tenure window |
| `primary_position` | match_team_lists | `mtl.named_position` (most-common in window) | SC writer uses SC position string; nrlcom writer uses match-centre position name |
| `height_cm` | SC players-cf | profile field | NULL for nrlcom-sourced rows |
| `weight_kg` | SC players-cf | profile field | NULL for nrlcom-sourced rows |
| `contract_until` | SC players-cf | profile field | NULL for nrlcom-sourced rows |
| `real_salary_aud` | not extracted | — | Reserved for future feed |
| `metadata_json` | extractor | `match_count`, `tenure_index`, `tenure_count`, `last_match` | nrlcom-sourced rows; SC writes its own keys |
| `effective_from` | match_team_lists | `MIN(matches.kickoff_at)` over the contiguous tenure | |
| `effective_to` | derived | `next_tenure.first_match - 1 day`, or `last_match` if closed, or NULL if current | |
| `is_current` | derived | true on the latest tenure if `last_match >= today - 365d` AND person doesn't have an SC-owned current row | SC-owned `is_current` is preserved (never competed with) |
| `source` | constant | `'supercoach'` ⊕ `'nrlcom/match-centre'` | Per writer |
| `created_at` | derived | — | DB default `now()` |
| `updated_at` | derived | — | Auto-updates |

## Trust hierarchy

- SC owns `is_current=true` for SC-eligible players. The nrlcom phase explicitly checks `source='supercoach' AND is_current` and refuses to compete on the unique partial index `uq_player_attributes_current`.
- For historical/non-SC people, nrlcom phase marks the most-recent tenure `is_current=true` only if the player's last match was within 365 days; otherwise all tenures are closed.

## UPSERT semantics (nrlcom phase)

- Natural key: `(person_id, team_id, effective_from) WHERE source='nrlcom/match-centre'` (mig 067)
- Pre-step: clear all `is_current=true` rows for this person within `source='nrlcom/match-centre'` so the unique partial index doesn't fire when re-marking a different tenure as current
- UPSERT preserves the row's `id` so any downstream FKs stay valid across re-runs (mig 067 — UPSERT not DELETE)

## Notes

- Coaches (`jersey_number IS NULL` rows in `match_team_lists`) are skipped — their tenures need [people_roles](people_roles.md), not `player_attributes`.
- Renamed from `people_attributes` in mig 068.
