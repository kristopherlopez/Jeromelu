---
tags: [area/operations, data-lineage]
---

# Lineage: outcomes

[Schema: data-catalogue/outcomes.md](../data-catalogue/outcomes.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Match results ([matches](matches.md)) | — | Resolves `prediction_id`-linked outcomes for match-bound predictions |
| SC scoring ([player_rounds](player_rounds.md)) | — | Resolves player/team performance predictions |
| Manual scoring | — | Subjective "called it right" judgement when no machine-readable proxy exists |

## Writer

Resolver job (scheduled per round) — reads predictions + decisions with `resolved_at IS NULL`, looks up the corresponding fact row (match score, player score, ladder position, etc.), and INSERTs an `outcomes` row with the result.

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `outcome_id` | derived | UUID, DB-side default |
| `prediction_id` | resolver | FK → predictions; NULL if scoring a decision |
| `decision_id` | resolver | FK → decisions; NULL if scoring a prediction |
| `actual_value_json` | resolver | Structured fact (e.g. `{home_score: 24, away_score: 18}` for a margin prediction) |
| `result_label` | resolver | Short verdict: `correct`, `incorrect`, `partial` |
| `scored_at` | derived | DB default `now()` |

## Notes

- Once an outcome is written, the upstream prediction's `resolution_status` and `resolved_at` are also UPDATEd (resolver writes both sides).
- Powers [alignment_scores](alignment_scores.md) (planned) — per-person accuracy roll-up.
