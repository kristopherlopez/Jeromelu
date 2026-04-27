# The Wiki

Status: **Phase 1 — Vertical slice built**

Route: `/wiki`
Code: `services/web/src/app/wiki/`

---

## Summary

A prose-dominant, agent-maintained knowledge base about the NRL, with SuperCoach as a subset. Users browse interlinked entity pages written and maintained by Jaromelu. [The Feed](../feed/overview.md) shows how the agent is actively improving the wiki.

Adapted from the [LLM Wiki pattern](llm-wiki-pattern.md) — the key difference from RAG is that knowledge is **compiled once and kept current**, not re-derived on every query.

See also: [Page design](page-design.md) · [Content pipeline](content-pipeline.md)

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage | New `wiki_pages` table (not evolving KB) | KB serves RAG (embeddings, expiry). Wiki serves browsing (sections, revisions, slugs). Different concerns. |
| Content format | Markdown with `[[slug]]` wiki-links | LLMs write markdown naturally. `##` headings define sections. Frontend parses and renders. |
| Slug convention | Full-name slugs (`tom-trbojevic`, `melbourne-storm`) | Unique, URL-safe. Round slugs prefixed (`round-2026-7`). |
| Navigation | Structural (metadata queries + link traversal) | No vector search needed for wiki. Agent reads index, follows links. |
| Maintenance model | Agent rewrites sections on new data | Continuous compilation. Prose synthesises across all sources. |
| Page format | Prose-dominant | Wiki articles, not dashboards. Structured data in sidebar or sections. |
| Revision tracking | Separate `wiki_revisions` table | Logs what changed, when, why. Powers feed + activity sidebar. |

---

## Page Types

### Phase 1 (MVP)

| Type | Route | Example | Backed by |
|------|-------|---------|-----------|
| Player | `/wiki/player/[slug]` | `/wiki/player/tom-trbojevic` | `entities` |
| Team | `/wiki/team/[slug]` | `/wiki/team/melbourne-storm` | `entities` |
| Channel | `/wiki/channel/[slug]` | `/wiki/channel/sc-playbook-youtube` | `channels` |
| Advisor | `/wiki/advisor/[slug]` | `/wiki/advisor/tim-williams` *(deferred)* | `entities` (advisor role) |
| Round | `/wiki/round/[season]/[round]` | `/wiki/round/2026/7` | `entities` |

Rounds include game subsections within the page content.

**Channel vs Advisor.** A *channel* is the outlet (SC Playbook YouTube, NRL Physio
Twitter); an *advisor* is the person/voice (Tim Williams, Brien Seeney). Channels
have authoritative records and are seeded from the `channels` table; advisor
pages are deferred until speaker diarisation provides confident person-level
attribution. In the index, both surface under the **Voices** tab.

`wiki_pages.entity_id` is now nullable; the new `channel_id` FK points to
`channels` for channel-typed pages. Exactly one of `entity_id` / `channel_id` is
set per row, enforced by `ck_wiki_page_subject`.

### Phase 2

- Coach pages (`/wiki/coach/[slug]`)
- Referee pages (`/wiki/referee/[slug]`)
- Commentator pages (`/wiki/commentator/[slug]`)
- Journalist pages (`/wiki/journalist/[slug]`)
- Topic/concept pages (agent-discovered)

The underlying entity types (`coach`, `referee`, `commentator`, `journalist`) are
already valid in `entities.entity_type` from migration `018_entity_roles.sql`.
Wiki page templates and routes for them ship as Phase 2 lands.

### Roles vs entity types

A single person can hold multiple roles over time (Andrew Johns: player → commentator;
Michael Ennis: coach + commentator concurrently). Identity is one entity row, with
role tenure tracked in the `entity_roles` table. `entities.entity_type` carries the
*current primary role* — used to drive the wiki page route. See
[Entity roles](../../concepts/entity-roles.md) for the SCD-2 pattern and worked examples.

The `expert` entity type was deprecated in migration 018 (use `advisor`).

---

## Database Schema

### wiki_pages

| Column | Type | Notes |
|--------|------|-------|
| page_id | UUID PK | |
| entity_id | UUID FK→entities, nullable | One page per entity for entity-backed pages |
| channel_id | UUID FK→channels, nullable | For channel-backed pages |
| page_type | TEXT | player, team, advisor, channel, round |
| slug | TEXT UNIQUE | URL slug |
| title | TEXT | Display name |
| content | TEXT | Markdown with `[[slug]]` wiki-links |
| summary | TEXT | One-liner for listings |
| metadata_json | JSONB | Tags, structured sidebar data |
| status | TEXT | stub → draft → published |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | Auto-update |

`ck_wiki_page_subject` enforces exactly one of `entity_id` / `channel_id` is set.

### wiki_revisions

| Column | Type | Notes |
|--------|------|-------|
| revision_id | UUID PK | |
| page_id | UUID FK→wiki_pages | CASCADE |
| section_heading | TEXT | NULL = full page |
| summary | TEXT | Agent-written change description |
| content_snapshot | TEXT | Optional section snapshot |
| source_trigger | TEXT | What caused this edit |
| source_id | UUID FK→sources | Optional |
| metadata_json | JSONB | |
| created_at | TIMESTAMPTZ | |

Migrations:
- `packages/db/migrations/015_wiki.sql` — initial schema
- `packages/db/migrations/018_entity_roles.sql` — SCD-2 entity roles + new people types
- `packages/db/migrations/019_wiki_channels.sql` — channel page type, channel_id FK, seeded 47 channel pages

---

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/wiki/pages` | List pages. Filters: `page_type`, `status`, `q`. Cursor pagination. Returns `metadata_json` per page for team/position/price grouping. |
| `GET /api/wiki/pages/{slug}` | Full page detail + revisions + `linked_pages` map |
| `GET /api/wiki/pages/{slug}/revisions` | Full revision history |
| `GET /api/wiki/recent-changes` | Recent revisions across all pages |

The `linked_pages` response field maps each `[[slug]]` found in the content to `{title, page_type}`, enabling the frontend to render wiki-links with correct display names and routes without extra API calls.

---

## Content Format

The agent writes markdown with:
- `##` headings for sections (Overview, Current Form, Price Analysis, Expert Opinions, etc.)
- `[[entity-slug]]` for cross-references to other wiki pages
- Standard markdown formatting (bold, lists, tables, blockquotes)

The frontend pre-processes `[[slug]]` into Next.js `<Link>` components using the `linked_pages` map from the API. Unknown slugs render as bold text.

---

## Feed Integration (Phase 2)

Two granularity levels:
- **Insight-level** — Agent surfaces notable changes: contradictions between advisors, big shifts in sentiment, prediction outcomes
- **Batch-level** — "Processed SC Playbook Round 7 — updated 12 pages"

Feed items link to the entity page scrolled to the changed section via anchor links.

Implemented via new `display_mode='wiki_update'` on the Event table.

---

## Advisor Accuracy Tracking (Phase 3)

- `advisor_predictions` table tracks verifiable calls per advisor
- Post-round resolution compares predictions against `PlayerRound` actuals
- Advisor wiki pages get `## Track Record` section with accuracy stats, notable hits/misses

---

## Key Files

| File | Purpose |
|------|---------|
| `packages/db/migrations/015_wiki.sql` | Schema |
| `packages/shared/jeromelu_shared/db/models.py` | WikiPage, WikiRevision models |
| `services/api/app/routers/wiki.py` | API router |
| `services/web/src/app/wiki/` | All frontend wiki pages and components |
| `scripts/data/seed_wiki.py` | One-time seed from existing KB entries |

---

## Related Documents

- [Content pipeline](content-pipeline.md) — sources, cleaning, and the managed agent update flow
- [Page design](page-design.md) — wiki colour palette, typography, component vocabulary
- [LLM Wiki pattern](llm-wiki-pattern.md) — the underlying pattern this wiki is built on
