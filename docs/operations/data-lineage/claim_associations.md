---
tags: [area/operations, data-lineage]
---

# Lineage: claim_associations

[Schema: data-catalogue/claim_associations.md](../data-catalogue/claim_associations.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| `process-transcript` / `upload-transcript` skills | — | Subject + context resolution |

## Writer

`scripts/transcripts/extraction/writer.py` — driven by the `upload-transcript` skill. For each [claims](claims.md) row, resolves the subject (and any contextual entities) to typed FKs and writes one association row per typed reference. SC notes path uses the same writer via `services/api/app/scout/supercoach_roster/notes_extractor.py`.

Example: a "Reece Walsh is a buy this week against the Storm" claim writes:
- `(claim_id, role='subject', person_id=reece_walsh)`
- `(claim_id, role='opponent', team_id=storm)`

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `association_id` | derived | UUID, DB-side default |
| `claim_id` | extractor | FK → claims (CASCADE) |
| `role` | extractor | `subject`, `context`, `opponent`, `mentioned`, ... |
| `person_id` | extractor (resolved) | FK → people (CASCADE). One typed FK is set per row. |
| `team_id` | extractor (resolved) | FK → teams (CASCADE) |
| `match_id` | extractor (resolved) | FK → matches (CASCADE) |
| `venue_id` | extractor (resolved) | FK → venues (CASCADE) |
| `round_id` | extractor (resolved) | FK → rounds (CASCADE) |

## Constraint

`ck_claim_associations_one_subject` enforces exactly one of `person_id` / `team_id` / `match_id` / `venue_id` / `round_id` per row. Replaces the old polymorphic `subject_entity_id` UUID — see [refactor-entities-to-typed-tables](../refactor-entities-to-typed-tables.md).

## Notes

- Same Option-B shape as [prediction_associations](prediction_associations.md) and [decision_associations](decision_associations.md).
- A claim can name multiple typed subjects with different roles; the unique constraint is `(claim_id, role, person_id, team_id, match_id, venue_id, round_id) NULLS NOT DISTINCT`.
