---
tags: [area/operations, data-catalogue]
---

# predictions

[← Data Catalogue](README.md) · [Lineage](../data-lineage/predictions.md) · Layer 4 — Reasoning & output

Forecasts about future events, linked to evidence claims. Subject(s) live on [prediction_associations](prediction_associations.md).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| prediction_id | UUID | PK | uuid4 | |
| predictor_person_id | UUID | yes | | FK → people (who made the prediction) |
| prediction_type | text | yes | | |
| predicted_value_text | text | yes | | |
| event_window | text | yes | | e.g. "Round 5", "2026 season" |
| evidence_claim_ids | UUID[] | no | [] | Array of claim_ids backing this |
| created_at | timestamptz | no | now() | |
| resolved_at | timestamptz | yes | | When outcome was determined |
| resolution_status | text | yes | | |

**Indexes:** predictor_person_id
**FK:** predictor_person_id → people
