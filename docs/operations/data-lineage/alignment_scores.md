---
tags: [area/operations, data-lineage, status/planned]
---

# Lineage: alignment_scores — planned (not yet built)

[Schema: data-catalogue/alignment_scores.md](../data-catalogue/alignment_scores.md)

## Status

Will be built when the Ledger surface lights up ([[project_ledger_direction]]).

## Planned source / writer

Per-person prediction-accuracy aggregator. Reads:
- [predictions](predictions.md) `predictor_person_id`
- [outcomes](outcomes.md) `prediction_id`, `result_label`

Computes per-(person, score_type, period) accuracy, writes to `alignment_scores`.

## Planned subject

Typed-nullable FKs + CHECK exactly-one (same Option-B as [claim_associations](claim_associations.md)) — likely just `person_id` since alignment is per-human.

## Notes

Powers The Ledger's Alignment Index (the "who's been right and how often" surface).
