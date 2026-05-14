---
tags: [area/operations, data-catalogue, status/planned]
---

# remarks — planned (not yet built)

[← Data Catalogue](README.md) · [Lineage](../data-lineage/remarks.md) · Layer 4 — Reasoning & output

> **Status:** described below as planned design — not yet present in `models.py` or migrations. Will be revisited as the front-end build clarifies whether this stays a distinct table from [predictions](predictions.md) / [decisions](decisions.md). See [docs/concepts/02-remarks.md](../../concepts/02-remarks.md) for the design intent. Subjects will use a `remark_associations` junction following the same Option-B shape as [claim_associations](claim_associations.md).

The atomic output unit: an opinionated, voiced analytical piece with an open → locked → resolved lifecycle.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| remark_id | UUID | PK | uuid4 | |
| voice_text | text | no | | Jaromelu's voiced output |
| position | text | yes | | `buy`, `sell`, `hold`, `captain`, `avoid` |
| conviction | text | yes | | `low`, `medium`, `high` |
| status | text | no | `open` | `open`, `locked`, `resolved` |
| evidence_claim_ids | UUID[] | no | [] | Upstream claims backing this |
| decision_id | UUID | yes | | FK → decisions |
| resolution_json | jsonb | yes | | Outcome data once resolved |
| resolved_at | timestamptz | yes | | |
| round | int | yes | | |
| season | int | yes | | |
| created_at | timestamptz | no | now() | |
| immutable_hash | text | yes | | SHA256 of remark payload |

**Indexes:** status, (round, season)
**FK:** decision_id → decisions

Subjects (players/teams/matches/venues/rounds the remark is about) live on a planned `remark_associations` junction with the same shape as [claim_associations](claim_associations.md).
