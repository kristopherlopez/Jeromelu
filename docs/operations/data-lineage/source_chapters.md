---
tags: [area/operations, data-lineage]
---

# Lineage: source_chapters

[Schema: data-catalogue/source_chapters.md](../data-catalogue/source_chapters.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| `analyse-transcript` skill | — | **Primary** — semantic chapter detection |

Optional secondary input: YouTube video description chapter timestamps (often present in `sources.description`) can seed initial chapter boundaries.

## Writer

- `analyse-transcript` skill — hierarchical multi-agent pipeline that detects semantic chapters in a [source_documents](source_documents.md) row and writes one `source_chapters` row per chapter with title + summary

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `chapter_id` | derived | UUID, DB-side default |
| `document_id` | scope | FK → source_documents (CASCADE) |
| `ordinal` | analyser | Order within document; UNIQUE with document_id |
| `title` | analyser | Short label (LLM-generated) |
| `summary` | analyser | Agent-written paragraph |
| `start_ts`, `end_ts` | analyser | Seconds |
| `created_at` | derived | DB default `now()` |

## Notes

- Used by `analyse-transcript` to scope claim extraction (each chapter gets its own specialist agent with chapter-scoped context).
- Used by UI for chapter navigation when reviewing a transcript.
