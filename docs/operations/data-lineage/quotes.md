---
tags: [area/operations, data-lineage]
---

# Lineage: quotes

[Schema: data-catalogue/quotes.md](../data-catalogue/quotes.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| `analyse-transcript` / `process-transcript` skills | — | **Primary** — quote extraction from cleaned transcript spans |
| SC `notes_extractor` | [data-sources/supercoach/classic-players-cf.md](../data-sources/supercoach/classic-players-cf.md) | Pulls `notes[]` from SC players-cf as 1:1 quotes (846 rows shipped) |

## Writers

- `services/api/app/miner/supercoach_roster/notes_extractor.py` — SC notes extractor; one quote per SC player note
- `upload-transcript` skill — persists Analyst-extracted quotes from a processed transcript

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `quote_id` | derived | UUID, DB-side default |
| `document_id` | extractor | FK → source_documents |
| `chunk_id` | extractor | FK → source_chunks (the chunk the quote was extracted from) |
| `speaker_person_id` | extractor | FK → people (resolved via [source_speakers](source_speakers.md) overlay or SC author) |
| `quoted_text` | extractor | The literal extracted text |
| `start_offset`, `end_offset` | extractor | Character offsets in the cleaned document |
| `said_at_reference` | extractor | Temporal reference in source (e.g. "earlier this week") |
| `confidence` | extractor | LLM extraction confidence 0-1 |
| `created_at` | derived | DB default `now()` |

## Notes

- For SC notes, one quote == one [claims](claims.md) row — they are 1:1 (846 quotes ↔ 846 claims as of last backfill).
- For analyst-extracted quotes, multiple [claims](claims.md) can reference the same quote.
