---
tags: [area/operations, data-catalogue]
---

# source_speakers

[← Data Catalogue](README.md) · [Lineage](../data-lineage/source_speakers.md) · Layer 3 — Content & claims

Diarised speaker turns over a document. Coarse-grained span layer above [source_chunks](source_chunks.md); chunks fall within a speaker turn by timestamp containment. Populated by the diarisation pass (Deepgram or equivalent) after document ingest.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| segment_id | UUID | PK | uuid4 | |
| document_id | UUID | no | | FK → source_documents (CASCADE) |
| speaker_person_id | UUID | yes | | FK → people (SET NULL); NULL for unattributed turns |
| speaker_label | text | yes | | Raw diariser label (`Speaker 1`) when person not yet resolved |
| start_ts | float | no | | Seconds |
| end_ts | float | no | | Seconds |
| confidence | float | yes | | Diarisation confidence 0-1 |
| created_at | timestamptz | no | now() | |

**Indexes:** document_id, speaker_person_id (partial: WHERE NOT NULL), (document_id, start_ts)
**FK:** document_id → source_documents (CASCADE); speaker_person_id → people (SET NULL)
