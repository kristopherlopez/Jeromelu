---
tags: [area/operations, data-lineage]
---

# Lineage: match_officials

[Schema: data-catalogue/match_officials.md](../data-catalogue/match_officials.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| nrl.com / match-centre | [data-sources/nrlcom/match-centre.md](../data-sources/nrlcom/match-centre.md) | **Primary** — `$.officials[*]` (4 rows per match: referee + touch judges + bunker) |

## Extractor

`scripts/data/populate/phase_timeline.py` — `populate_timeline_and_officials()` (combined writer with [match_timeline](match_timeline.md)). One pass over match-centre archives writes both. Idempotent UPSERT on `(nrlcom_match_id, first_name, last_name, COALESCE(role, ''))`. ~948 rows shipped.

## Field mapping

| DB column | Source | Source field | Notes |
|---|---|---|---|
| `id` | derived | — | UUID |
| `match_id` | resolved | via `matches.external_match_id` | |
| `nrlcom_match_id` | match-centre | `$.matchId` | Idempotency key part |
| `first_name` | match-centre | `$.officials[*].firstName` | Stripped |
| `last_name` | match-centre | `$.officials[*].lastName` | Stripped |
| `role` | match-centre | `$.officials[*].position` | `Referee`, `Touch Judge`, `Bunker`, etc. |
| `person_id` | not yet resolved | — | Officials don't share the players profile-id space cleanly — extractor leaves NULL today; resolution by name-match is a follow-up |
| `raw_payload` | match-centre | full official payload | |
| `s3_archive_key` | derived | the source key | |
| `created_at` | derived | DB default `now()` | |

## Notes

- `matches.referee_name` carries the lead-referee free-text for query convenience (resolved by `phase_matches.py` separately).
- See migration 058.
