---
tags: [area/operations, data-catalogue, status/planned]
---

# alignment_scores — planned (not yet built)

[← Data Catalogue](README.md) · Layer 4 — Reasoning & output

> **Status:** described below as planned design — not yet present in `models.py` or migrations. Will be built when the Ledger surface lights up. Subject will use typed-nullable FKs + CHECK exactly-one (same Option-B pattern as [claim_associations](claim_associations.md)) — likely just `person_id` since alignment is per-human.

Prediction accuracy tracking per person (expert, user, or system). Powers [The Ledger](../../pages/ledger/overview.md)'s Alignment Index.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| score_id | UUID | PK | uuid4 | |
| person_id | UUID | no | | FK → people |
| entity_type | text | no | | `expert`, `user`, `system` |
| score_type | text | no | | `overall`, `captain_picks`, `buy_sell`, `matchup` |
| period | text | no | | `round`, `month`, `season` |
| period_value | text | yes | | e.g. round number or season year |
| total_predictions | int | no | 0 | |
| correct_predictions | int | no | 0 | |
| alignment_pct | float | yes | | |
| updated_at | timestamptz | no | now() | |

**Indexes:** (person_id, score_type, period, period_value)
**FK:** person_id → people
