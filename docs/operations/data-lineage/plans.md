---
tags: [area/operations, data-lineage]
---

# Lineage: plans

[Schema: data-catalogue/plans.md](../data-catalogue/plans.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Jaromelu strategy synthesis | — | **Primary writer** |

## Writer

Reasoning agent (Bookkeeper / Critic per [[project_crew_terminology]]) — synthesises round-level strategy documents combining claims, predictions, scenarios, and the user's current squad state.

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `plan_id` | derived | UUID, DB-side default |
| `status` | writer | `draft`, `published`, `superseded` |
| `round_number` | writer | NRL round this plan targets |
| `plan_summary` | writer | Markdown narrative |
| `scenario_json` | writer | Structured trade scenarios, captain comparisons, value plays |
| `created_at` | derived | DB default `now()` |
| `updated_at` | derived | Auto-updates on change |
