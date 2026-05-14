---
tags: [area/operations, data-lineage]
---

# Lineage: source_documents

[Schema: data-catalogue/source_documents.md](../data-catalogue/source_documents.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| YouTube auto-captions (raw S3 archive) | — (raw transcripts in `data/transcripts/raw/`) | **Primary** for YouTube videos |
| Podcast transcription (Deepgram) | — | For podcast episodes ([[project_content_production]]) |
| Manual upload | — | Web articles, one-off transcripts |

## Writers

- `fetch-transcripts` skill (`scripts/transcripts/...`) — downloads YouTube auto-captions to `data/transcripts/raw/`, then writes the raw text into `source_documents.raw_text` and stores S3 key in `s3_key`
- `clean-transcript` skill — populates `cleaned_text` after running cleaning passes
- `upload-transcript` skill — finalises `transcript_available=true`, sets `chunk_count` after [source_chunks](source_chunks.md) are written

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `document_id` | derived | UUID, DB-side default |
| `source_id` | scope | FK → sources |
| `s3_key` | ingestion | S3 object key for the raw file |
| `raw_text` | ingestion | Original transcript text (auto-captions or Deepgram output) |
| `cleaned_text` | clean-transcript skill | Post-cleaning text (player names corrected, garbled words fixed, NRL terms preserved per [[reference_transcript_corrections]] and [[reference_nrl_slang]]) |
| `transcript_available` | upload-transcript | Set true once chunks land |
| `language` | ingestion | Defaults `en` |
| `checksum` | ingestion | Content hash for dedup |
| `chunk_count` | upload-transcript | Count of `source_chunks` rows for this document |
| `created_at` | derived | DB default `now()` |

## Notes

- One source can have multiple documents (e.g. raw captions + a refined manual transcript).
- The cleaning pass uses `[[reference_nrl_slang]]` (terms like "PVL" not to over-correct) and `[[reference_transcript_corrections]]` (confirmed garbles for player/team names).
