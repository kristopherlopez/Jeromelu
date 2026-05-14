---
tags: [area/operations, data-lineage]
---

# Lineage: predictions

[Schema: data-catalogue/predictions.md](../data-catalogue/predictions.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Jaromelu reasoning (forecasts derived from claims) | — | **Primary writer** — agent reasoning over upstream [claims](claims.md) |
| Direct claim → prediction projection | — | When a buy/sell/hold claim implies a measurable forecast |

## Writers

- Reasoning agents (Analyst / Critic per [[project_crew_terminology]]) — produce predictions with `evidence_claim_ids` referencing the upstream [claims](claims.md) that backed the call
- The Ledger surface ([[project_ledger_direction]]) — multi-source prediction tracking with future accuracy index

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `prediction_id` | derived | UUID, DB-side default |
| `predictor_person_id` | reasoning | FK → people. Either an external expert (commentator who made the call) or a synthetic Jaromelu/system identity |
| `prediction_type` | reasoning | e.g. `score_margin`, `try_scorer`, `captain_pick`, `weekly_high` |
| `predicted_value_text` | reasoning | Human-readable prediction |
| `event_window` | reasoning | e.g. `Round 5`, `2026 season` |
| `evidence_claim_ids` | reasoning | Array of `claim_id`s that backed the call |
| `created_at` | derived | DB default `now()` |
| `resolved_at` | resolver | When outcome was determined |
| `resolution_status` | resolver | `correct`, `incorrect`, `partial`, `unresolvable` |

## Subjects

Live in [prediction_associations](prediction_associations.md) — typed-FK exactly-one junction. The dominant case is one row with `role='subject'` per prediction.

## Notes

- The prediction tracking pattern is the foundation for [alignment_scores](alignment_scores.md) (planned) — once predictions resolve via [outcomes](outcomes.md), per-person accuracy aggregates per [[project_ledger_direction]].
