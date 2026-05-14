---
tags: [area/operations, data-catalogue]
---

# rounds

[← Data Catalogue](README.md) · Layer 1 — Identity

Round identity for the NRL/NRLW competition cycles. Referenced by claim/prediction/decision associations when an opinion is round-level rather than player- or match-level.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| round_id | UUID | PK | uuid4 | |
| season | int | no | | |
| round_number | int | yes | | NULL for finals — use `round_label` |
| round_label | text | no | | "Round 5", "Finals Week 1", "Magic Round" |
| starts_at | timestamptz | yes | | |
| ends_at | timestamptz | yes | | |
| is_magic_round | bool | no | false | |
| is_rep_weekend | bool | no | false | |
| is_finals | bool | no | false | |
| metadata_json | jsonb | no | {} | |

**Unique:** (season, round_number)
**Indexes:** season
