---
tags: [area/operations, data-lineage]
---

# Lineage: decisions

[Schema: data-catalogue/decisions.md](../data-catalogue/decisions.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Jaromelu reasoning (decisions taken from world + claims) | — | **Primary writer** |

## Writers

- Reasoning agents (Critic / Bookkeeper per [[project_crew_terminology]]) — propose decisions backed by claims and predictions
- User-confirmed actions — when a recommended decision is adopted, it's persisted with `executed_at`
- Article topic / reply selection — `decision_type='article_topic'` or `'reply'` records the system's choice of what to publish

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `decision_id` | derived | UUID, DB-side default |
| `decision_type` | writer | `trade`, `captain`, `start_sit`, `squad_structure`, `article_topic`, `reply` |
| `action_json` | writer | Structured payload (e.g. `{from: player_id, to: player_id}` for trades) |
| `rationale_summary` | writer | Free-text — why this decision was made |
| `strategy_tag` | writer | e.g. `value_play`, `safe_pivot`, `pre_bye` |
| `created_at` | derived | DB default `now()` |
| `executed_at` | writer | Set when the decision is confirmed/applied |
| `public_flag` | writer | Whether this decision is part of a public article |

## Subjects

Live in [decision_associations](decision_associations.md) — typed-FK exactly-one junction. Trade decisions typically have `role='player_in'` and `role='player_out'` rows; captain decisions have one `role='subject'`.

## Notes

- Squad / trade execution detail will live in [squad_slots / squad_trades](squad_slots.md) when the SuperCoach feature lights up.
