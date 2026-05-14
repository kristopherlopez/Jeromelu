---
tags: [area/operations, data-lineage]
---

# Lineage: prediction_associations

[Schema: data-catalogue/prediction_associations.md](../data-catalogue/prediction_associations.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Same writers as [predictions](predictions.md) | — | Subject + context resolution |

## Writer

Written together with each [predictions](predictions.md) row by the reasoning pipeline that produces the prediction.

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `association_id` | derived | UUID, DB-side default |
| `prediction_id` | reasoning | FK → predictions (CASCADE) |
| `role` | reasoning | `subject`, `context`, `opponent`, ... |
| `person_id` / `team_id` / `match_id` / `venue_id` / `round_id` | reasoning (resolved) | Exactly one is set per row (`ck_prediction_associations_one_subject`) |

## Notes

- Same Option-B shape as [claim_associations](claim_associations.md) and [decision_associations](decision_associations.md). Replaces the pre-mig-038 polymorphic `subject_entity_id`.
