---
tags: [area/operations, data-lineage]
---

# Lineage: wiki_pages

[Schema: data-catalogue/wiki_pages.md](../data-catalogue/wiki_pages.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Managed Archivist agent | — | **Primary** — agent maintains player/team/round/channel pages from claims + structured data |
| Manual seed (`scripts/data/seed_wiki.py`, `scripts/data/backfill_wiki_team_pages.py`) | — | Initial page creation |
| Manual edits | — | Direct authoring via wiki UI |

## Writers

- Archivist agent (per `docs/agents/crew/archivist.md` and the in-progress draft) — reads new claims/predictions and writes/updates wiki page content; emits a [wiki_revisions](wiki_revisions.md) row per change
- `scripts/data/seed_wiki.py` — bulk seed for initial wiki population
- `scripts/data/backfill_wiki_team_pages.py` — team-page backfill from `teams` rows

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `page_id` | derived | UUID, DB-side default |
| `person_id` / `team_id` / `match_id` / `venue_id` / `round_id` / `channel_id` | writer | Exactly one set (`ck_wiki_page_subject`) |
| `page_type` | writer | `player`, `team`, `advisor`, `round`, `channel` |
| `slug` | writer | UNIQUE; URL slug |
| `title` | writer | Display name |
| `content` | writer | Markdown with `[[slug]]` wiki-links |
| `summary` | writer | One-liner for listings |
| `metadata_json` | writer | Tags, sidebar data |
| `status` | writer | `stub`, `draft`, `published` |
| `created_at`, `updated_at` | derived | DB defaults |

## Notes

- `channel_id` was added by mig 019 to support channel-typed wiki pages.
- Powers The Wiki surface.
