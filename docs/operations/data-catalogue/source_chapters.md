---
tags: [area/operations, data-catalogue]
---

# source_chapters

[← Data Catalogue](README.md) · [Lineage](../data-lineage/source_chapters.md) · Layer 3 — Content & claims

Semantic chapters detected over a document. Used by the analyse-transcript pipeline to scope claim extraction and to attribute claims back to a chapter for UI navigation.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| chapter_id | UUID | PK | uuid4 | |
| document_id | UUID | no | | FK → source_documents (CASCADE) |
| ordinal | int | no | | Order within document |
| title | text | no | | Short label |
| summary | text | yes | | Agent-written summary |
| start_ts | float | no | | |
| end_ts | float | no | | |
| created_at | timestamptz | no | now() | |

**Unique:** (document_id, ordinal)
**Indexes:** document_id, (document_id, start_ts)
**FK:** document_id → source_documents (CASCADE)
