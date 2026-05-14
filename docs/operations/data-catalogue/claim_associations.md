---
tags: [area/operations, data-catalogue]
---

# claim_associations

[← Data Catalogue](README.md) · [Lineage](../data-lineage/claim_associations.md) · Layer 3 — Content & claims

Polymorphic many-to-many between claims and typed entities. A claim can name multiple typed subjects with different roles (e.g. a player as the subject + a team as context). The CHECK constraint enforces exactly one typed FK is set per row.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| association_id | UUID | PK | uuid4 | |
| claim_id | UUID | no | | FK → claims (CASCADE) |
| role | text | no | | `subject`, `context`, `opponent`, `mentioned`, ... |
| person_id | UUID | yes | | FK → people (CASCADE) |
| team_id | UUID | yes | | FK → teams (CASCADE) |
| match_id | UUID | yes | | FK → matches (CASCADE) |
| venue_id | UUID | yes | | FK → venues (CASCADE) |
| round_id | UUID | yes | | FK → rounds (CASCADE) |

**Check:** `(person_id IS NOT NULL)::int + (team_id IS NOT NULL)::int + (match_id IS NOT NULL)::int + (venue_id IS NOT NULL)::int + (round_id IS NOT NULL)::int = 1` (`ck_claim_associations_one_subject`)
**Unique:** (claim_id, role, person_id, team_id, match_id, venue_id, round_id) NULLS NOT DISTINCT
**Indexes:** claim_id, plus per-FK partial indexes WHERE NOT NULL
