---
tags: [area/operations, data-catalogue]
---

# people

[← Data Catalogue](README.md) · [Lineage](../data-lineage/people.md) · Layer 1 — Identity

Unified table for every human actor — players, coaches, advisors, commentators, journalists, referees. Lifetime-stable facts get typed columns; long-tail goes in `metadata_json`.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| person_id | UUID | PK | uuid4 | |
| canonical_name | text | no | | |
| aliases | text[] | no | `{}` | Alternative names/spellings |
| slug | text | yes | | UNIQUE; URL-safe slug |
| dob | date | yes | | Date of birth |
| country | text | yes | | `AU`, `NZ`, `UK`, `PNG`, ... |
| image_url | text | yes | | Profile/headshot URL |
| supercoach_id | int | yes | | UNIQUE; cross-system identifier (NULL for non-players) |
| metadata_json | jsonb | no | {} | Long-tail / sparse / unstructured (twitter handle, wikipedia URL, etc.) |
| created_at | timestamptz | no | now() | |

**Unique:** slug, supercoach_id
**Indexes:** canonical_name, country (partial: WHERE NOT NULL)
