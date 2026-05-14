---
tags: [area/operations, data-catalogue]
---

# wiki_revisions

[← Data Catalogue](README.md) · [Lineage](../data-lineage/wiki_revisions.md) · Layer 4 — Reasoning & output

Per-section edit log for wiki pages.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| revision_id | UUID | PK | uuid4 | |
| page_id | UUID | no | | FK → wiki_pages (CASCADE) |
| section_heading | text | yes | | Null = full page |
| summary | text | no | | Agent-written change description |
| content_snapshot | text | yes | | Optional snapshot of the section |
| source_trigger | text | yes | | e.g. `archivist/claims-upload` |
| source_id | UUID | yes | | FK → sources (optional) |
| metadata_json | jsonb | no | {} | |
| created_at | timestamptz | no | now() | |

**Indexes:** page_id, created_at
**FK:** page_id → wiki_pages (CASCADE); source_id → sources

Powers the wiki activity feed (`GET /api/wiki/recent-changes`).
