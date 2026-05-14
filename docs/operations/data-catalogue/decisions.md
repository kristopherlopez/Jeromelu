---
tags: [area/operations, data-catalogue]
---

# decisions

[← Data Catalogue](README.md) · Layer 4 — Reasoning & output

Action decisions made in the system (trades, captain picks, etc.). Subject(s) and contextual entities live on [decision_associations](decision_associations.md).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| decision_id | UUID | PK | uuid4 | |
| decision_type | text | no | | `trade`, `captain`, `start_sit`, `squad_structure`, `article_topic`, `reply` |
| action_json | jsonb | no | {} | Structured action payload |
| rationale_summary | text | yes | | |
| strategy_tag | text | yes | | |
| created_at | timestamptz | no | now() | |
| executed_at | timestamptz | yes | | |
| public_flag | bool | no | false | |

**Indexes:** decision_type
