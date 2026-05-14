---
tags: [area/operations, data-lineage]
---

# Lineage: decision_associations

[Schema: data-catalogue/decision_associations.md](../data-catalogue/decision_associations.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Same writers as [decisions](decisions.md) | — | Written together with each decision |

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `association_id` | derived | UUID, DB-side default |
| `decision_id` | reasoning | FK → decisions (CASCADE) |
| `role` | reasoning | `subject`, `player_in`, `player_out`, `context`, ... |
| `person_id` / `team_id` / `match_id` / `venue_id` / `round_id` | reasoning (resolved) | Exactly one per row (`ck_decision_associations_one_subject`) |

## Notes

- Same Option-B shape as [claim_associations](claim_associations.md) and [prediction_associations](prediction_associations.md).
- Trade decisions: paired `player_in` / `player_out` rows. Captain decisions: one `subject` row.
