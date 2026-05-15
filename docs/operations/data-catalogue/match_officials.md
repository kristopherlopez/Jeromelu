---
tags: [area/operations, data-catalogue]
---

# match_officials

[← Data Catalogue](README.md) · [Lineage](../data-lineage/match_officials.md) · Layer 2 — Structured world

Referees, touch judges, bunker per match from nrl.com match-centre. The `officials` array returns 4 entries per match. Added in mig 058.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| match_id | UUID | yes | | FK → matches (CASCADE) |
| nrlcom_match_id | text | no | | nrl.com matchId |
| first_name | text | no | | |
| last_name | text | no | | |
| role | text | yes | | `Referee`, `Touch Judge`, `Bunker`, etc. |
| person_id | UUID | yes | | FK → people; nullable, resolved when extractor matches name |
| raw_payload | jsonb | no | | |
| s3_archive_key | text | yes | | |
| created_at | timestamptz | no | now() | |

**Unique:** `(nrlcom_match_id, first_name, last_name, COALESCE(role, ''))`
**Indexes:** match_id, person_id (partial: WHERE NOT NULL)
**FK:** match_id → matches (CASCADE); person_id → people

`matches.referee_name` carries the lead-referee free-text for query convenience. This table carries the full officials roster.
