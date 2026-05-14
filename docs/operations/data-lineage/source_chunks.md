---
tags: [area/operations, data-lineage]
---

# Lineage: source_chunks

[Schema: data-catalogue/source_chunks.md](../data-catalogue/source_chunks.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Source document (deduped auto-caption segments) | — | **Primary** — 1:1 with caption segments |

## Writers

- `scripts/transcripts/extraction/chunker.py` — splits `source_documents.cleaned_text` into 5-6 word segments preserving original YouTube caption boundaries and timestamps
- `clean-transcript` skill — calls the chunker after cleaning
- `upload-transcript` skill — INSERTs the resulting chunks

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `chunk_id` | derived | UUID, DB-side default |
| `document_id` | scope | FK → source_documents |
| `chunk_index` | derived | Monotonic ordering within document |
| `raw_text` | source document | Original auto-caption segment |
| `clean_text` | clean-transcript pass | Corrected player names, fixed garbled words |
| `start_offset`, `end_offset` | chunker | Character offsets in the cleaned text |
| `start_ts`, `end_ts` | source captions | Video/audio timestamp (seconds) |
| `embedding` | future | OpenAI ada-002 (1536d); not always populated |
| `created_at` | derived | DB default `now()` |

## Notes

- Atomic caption-level unit. Higher-level overlays ([source_speakers](source_speakers.md), [source_chapters](source_chapters.md)) sit *above* chunks at the document level; chunks fall within those spans by timestamp containment.
- Embeddings are populated lazily for documents that need RAG retrieval (e.g. when a [knowledge_base](knowledge_base.md) entry is built from this source).
