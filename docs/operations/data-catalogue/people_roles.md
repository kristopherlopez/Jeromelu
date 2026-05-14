---
tags: [area/operations, data-catalogue]
---

# people_roles

[← Data Catalogue](README.md) · Layer 1 — Identity

SCD-2 of role tenure per person. **Multi-valued at a single point in time** — a person can hold multiple roles concurrently (Adam Reynolds = active player + occasional commentator) or transition (Andrew Johns: player → commentator). Replaces `entity_roles`.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| role_id | UUID | PK | uuid4 | |
| person_id | UUID | no | | FK → people (CASCADE) |
| role | text | no | | `player`, `coach`, `commentator`, `journalist`, `referee`, `advisor` |
| effective_from | date | no | | Start of tenure |
| effective_to | date | yes | | End of tenure (NULL = current) |
| is_primary | bool | no | false | Exactly one primary current row per person |
| metadata_json | jsonb | no | {} | |
| source | text | no | `seed` | `seed`, `backfill_036`, `manual`, ... |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | |

**Indexes:** (person_id, effective_to), (role, effective_from, effective_to)
**Unique partial index:** person_id WHERE is_primary AND effective_to IS NULL — exactly one primary current role per person
**Check:** `effective_to IS NULL OR effective_to >= effective_from`
**FK:** person_id → people (CASCADE)

To filter "current commentators": `WHERE role='commentator' AND is_primary AND effective_to IS NULL`. There is no denormalised `people.entity_type` — JOIN to this table when you need the role.
