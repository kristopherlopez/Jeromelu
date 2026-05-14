---
tags: [area/operations, data-catalogue]
---

# wiki_pages

[← Data Catalogue](README.md) · Layer 4 — Reasoning & output

Prose per-entity (or per-channel) knowledge pages, written and maintained by a managed agent.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| page_id | UUID | PK | uuid4 | |
| person_id | UUID | yes | | FK → people |
| team_id | UUID | yes | | FK → teams |
| match_id | UUID | yes | | FK → matches |
| venue_id | UUID | yes | | FK → venues |
| round_id | UUID | yes | | FK → rounds |
| channel_id | UUID | yes | | FK → channels (set for `channel`-typed pages, mig 019) |
| page_type | text | no | | `player`, `team`, `advisor`, `round`, `channel` |
| slug | text | no | | URL slug, unique |
| title | text | no | | Display name |
| content | text | no | "" | Markdown with `[[slug]]` wiki-links |
| summary | text | yes | | One-liner for listings |
| metadata_json | jsonb | no | {} | Tags, sidebar data |
| status | text | no | `stub` | `stub`, `draft`, `published` |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | Auto-updates |

**Unique:** slug
**Check:** exactly-one of person_id / team_id / match_id / venue_id / round_id / channel_id is set (`ck_wiki_page_subject`)
**Indexes:** page_type, slug, channel_id, updated_at, status
**FK:** person_id → people; team_id → teams; match_id → matches; venue_id → venues; round_id → rounds; channel_id → channels

Powers [The Wiki](../../pages/wiki/overview.md).
