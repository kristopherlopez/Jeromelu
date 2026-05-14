---
tags: [area/operations, data-catalogue]
---

# claim_chunks

[← Data Catalogue](README.md) · [Lineage](../data-lineage/claim_chunks.md) · Layer 3 — Content & claims

Junction table linking claims to the source chunks they were extracted from (N:M).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| claim_id | UUID | PK | | FK → claims (CASCADE delete) |
| chunk_id | UUID | PK | | FK → source_chunks (CASCADE delete) |
| ordinal | int | no | 0 | Ordering of chunks for this claim |

**Indexes:** chunk_id
**Composite PK:** (claim_id, chunk_id)
