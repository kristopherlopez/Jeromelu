---
tags: [area/operations, data-catalogue]
---

# outcomes

[← Data Catalogue](README.md) · [Lineage](../data-lineage/outcomes.md) · Layer 4 — Reasoning & output

Scored results for predictions and decisions after events occur.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| outcome_id | UUID | PK | uuid4 | |
| prediction_id | UUID | yes | | FK → predictions |
| decision_id | UUID | yes | | FK → decisions |
| actual_value_json | jsonb | yes | | |
| result_label | text | yes | | |
| scored_at | timestamptz | no | now() | |

**FK:** prediction_id → predictions; decision_id → decisions
