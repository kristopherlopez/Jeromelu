---
tags: [area/operations, data-catalogue]
---

# quotes

[← Data Catalogue](README.md) · Layer 3 — Content & claims

Direct quotes extracted from source documents, attributed to a speaker.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| quote_id | UUID | PK | uuid4 | |
| document_id | UUID | no | | FK → source_documents |
| chunk_id | UUID | yes | | FK → source_chunks |
| speaker_person_id | UUID | yes | | FK → people |
| quoted_text | text | no | | |
| start_offset | int | yes | | Character offset |
| end_offset | int | yes | | Character offset |
| said_at_reference | text | yes | | Temporal reference in source |
| confidence | float | yes | | Extraction confidence 0-1 |
| created_at | timestamptz | no | now() | |

**Indexes:** document_id, speaker_person_id
**FK:** document_id → source_documents; chunk_id → source_chunks; speaker_person_id → people
