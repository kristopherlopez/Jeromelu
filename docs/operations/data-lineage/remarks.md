---
tags: [area/operations, data-lineage, status/planned]
---

# Lineage: remarks — planned (not yet built)

[Schema: data-catalogue/remarks.md](../data-catalogue/remarks.md)

## Status

Not yet present in `models.py` or migrations. Will be revisited as the front-end build clarifies whether this stays a distinct table from [predictions](predictions.md) / [decisions](decisions.md). See `docs/concepts/02-remarks.md` for the design intent.

## Planned writer

Reasoning agents emit voiced analytical pieces (Jaromelu's voice) with an open → locked → resolved lifecycle. `evidence_claim_ids` references upstream [claims](claims.md).

## Planned subjects

A `remark_associations` junction following the same Option-B shape as [claim_associations](claim_associations.md) (typed-FK exactly-one).

## Notes

The atomic output unit Jaromelu publishes. Until the front-end build pins the contract, no extractor exists.
