---
tags: [area/operations, data-catalogue]
---

# source_documents

[← Data Catalogue](README.md) · [Lineage](../data-lineage/source_documents.md) · Layer 3 — Content & claims

Full transcript or text content for a source. One source can have multiple documents.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| document_id | UUID | PK | uuid4 | |
| source_id | UUID | no | | FK → sources |
| s3_key | text | yes | | S3 object key for raw file |
| raw_text | text | yes | | Original transcript text |
| cleaned_text | text | yes | | Post-cleaning text |
| transcript_available | bool | no | false | |
| language | text | no | `en` | |
| checksum | text | yes | | Content hash for dedup |
| chunk_count | int | no | 0 | |
| created_at | timestamptz | no | now() | |

**Indexes:** source_id
**FK:** source_id → sources.source_id
