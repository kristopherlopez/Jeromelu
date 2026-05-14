---
tags: [area/operations, data-catalogue]
---

# prediction_associations

[← Data Catalogue](README.md) · Layer 4 — Reasoning & output

Polymorphic many-to-many between predictions and typed entities. Same shape as [claim_associations](claim_associations.md) — one row with `role='subject'` per prediction is the dominant case.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| association_id | UUID | PK | uuid4 | |
| prediction_id | UUID | no | | FK → predictions (CASCADE) |
| role | text | no | | `subject`, `context`, `opponent`, ... |
| person_id | UUID | yes | | FK → people (CASCADE) |
| team_id | UUID | yes | | FK → teams (CASCADE) |
| match_id | UUID | yes | | FK → matches (CASCADE) |
| venue_id | UUID | yes | | FK → venues (CASCADE) |
| round_id | UUID | yes | | FK → rounds (CASCADE) |

**Check:** exactly-one of typed FKs (`ck_prediction_associations_one_subject`)
**Unique:** (prediction_id, role, person_id, team_id, match_id, venue_id, round_id) NULLS NOT DISTINCT
**Indexes:** prediction_id, plus per-FK partial indexes WHERE NOT NULL
