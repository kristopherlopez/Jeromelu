---
tags: [area/operations, data-catalogue]
---

# source_chunks

[← Data Catalogue](README.md) · Layer 3 — Content & claims

Individual transcript segments (1:1 with deduped auto-caption segments). Each row is a single 5-6 word segment preserving the original YouTube caption boundaries and timestamps.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| chunk_id | UUID | PK | uuid4 | |
| document_id | UUID | no | | FK → source_documents |
| chunk_index | int | no | | Ordering within document |
| raw_text | text | no | | Original auto-caption text |
| clean_text | text | yes | | Post-cleaning text (corrected names, garbled words) |
| start_offset | int | yes | | Character offset in document |
| end_offset | int | yes | | Character offset in document |
| start_ts | float | yes | | Video/audio timestamp (seconds) |
| end_ts | float | yes | | Video/audio timestamp (seconds) |
| embedding | vector(1536) | yes | | pgVector, OpenAI ada-002 dimensions |
| created_at | timestamptz | no | now() | |

**Indexes:** document_id
**FK:** document_id → source_documents.document_id
