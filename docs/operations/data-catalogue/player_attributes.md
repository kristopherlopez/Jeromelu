---
tags: [area/operations, data-catalogue]
---

# player_attributes

[← Data Catalogue](README.md) · Layer 1 — Identity

SCD-2 of slow-changing per-person facts (team affiliation, primary position, height/weight, contract). Replaces the old `player_attributes` table. Closed and reopened on change.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| person_id | UUID | no | | FK → people (CASCADE) |
| team_id | UUID | yes | | FK → teams (SET NULL); parent NRL/NRLW row even when player is on a feeder grade |
| primary_position | text | yes | | SC position string (FRF, HOK, HFB, ...) |
| height_cm | int | yes | | |
| weight_kg | int | yes | | |
| contract_until | date | yes | | Real-world contract end |
| real_salary_aud | int | yes | | Reserved for future feed; NULL today |
| metadata_json | jsonb | no | {} | secondary_positions etc. (long-tail; promote to columns when heavily queried) |
| effective_from | date | no | | Start of this state |
| effective_to | date | yes | | End of state (NULL = current) |
| is_current | bool | no | true | |
| source | text | no | `seed` | `supercoach`, `nrl_com`, `nswrl_com`, `qrl_com`, `seed`, ... |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | Auto-updates |

**Indexes:** (person_id, is_current), (team_id, is_current)
**Unique partial index:** person_id WHERE is_current — exactly one current row per person
**Check:** `effective_to IS NULL OR effective_to >= effective_from`
**FK:** person_id → people (CASCADE); team_id → teams (SET NULL)

Lifetime constants (dob, country) live on [people](people.md); per-round facts (price, breakeven, score, jersey, grade) live on [player_rounds](player_rounds.md).
