---
tags: [area/operations, data-catalogue]
---

# plans

[← Data Catalogue](README.md) · Layer 4 — Reasoning & output

Strategy documents per round.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| plan_id | UUID | PK | uuid4 | |
| status | text | no | `draft` | |
| round_number | int | yes | | |
| plan_summary | text | yes | | |
| scenario_json | jsonb | no | {} | |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | Auto-updates on change |
