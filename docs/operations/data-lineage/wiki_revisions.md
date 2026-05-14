---
tags: [area/operations, data-lineage]
---

# Lineage: wiki_revisions

[Schema: data-catalogue/wiki_revisions.md](../data-catalogue/wiki_revisions.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Same writers as [wiki_pages](wiki_pages.md) | — | One revision row per page edit |

## Writer

Every `UPDATE wiki_pages SET content = ...` (whether from Archivist agent, seed scripts, or manual edits) produces a corresponding `wiki_revisions` INSERT capturing what changed.

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `revision_id` | derived | UUID, DB-side default |
| `page_id` | writer | FK → wiki_pages (CASCADE) |
| `section_heading` | writer | NULL = full page edit; otherwise the heading of the edited section |
| `summary` | writer | Agent-written change description (e.g. "Added Round 7 stat update") |
| `content_snapshot` | writer | Optional snapshot of the section as it was after the edit |
| `source_trigger` | writer | e.g. `archivist/claims-upload`, `seed`, `manual` |
| `source_id` | writer | FK → sources (optional — if the edit was triggered by a specific upstream source) |
| `metadata_json` | writer | Free-form |
| `created_at` | derived | DB default `now()` |

## Notes

- Powers the wiki activity feed (`GET /api/wiki/recent-changes`).
- Cascade delete from `wiki_pages` keeps history tidy if a page is removed.
