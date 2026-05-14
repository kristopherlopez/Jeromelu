---
tags: [area/operations, data-catalogue]
---

# decision_associations

[← Data Catalogue](README.md) · Layer 4 — Reasoning & output

Polymorphic many-to-many between decisions and typed entities. Trade decisions typically have `role='player_in'` and `role='player_out'` rows pointing at people; captain decisions have one `role='subject'` person; etc.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| association_id | UUID | PK | uuid4 | |
| decision_id | UUID | no | | FK → decisions (CASCADE) |
| role | text | no | | `subject`, `player_in`, `player_out`, `context`, ... |
| person_id | UUID | yes | | FK → people (CASCADE) |
| team_id | UUID | yes | | FK → teams (CASCADE) |
| match_id | UUID | yes | | FK → matches (CASCADE) |
| venue_id | UUID | yes | | FK → venues (CASCADE) |
| round_id | UUID | yes | | FK → rounds (CASCADE) |

**Check:** exactly-one of typed FKs (`ck_decision_associations_one_subject`)
**Unique:** (decision_id, role, person_id, team_id, match_id, venue_id, round_id) NULLS NOT DISTINCT
**Indexes:** decision_id, plus per-FK partial indexes WHERE NOT NULL
