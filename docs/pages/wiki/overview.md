---
tags: [area/pages, subarea/wiki]
---

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

### Index entry views

`/wiki?type=<entity>` lands on a per-entity index. Two of these have bespoke
shells; the rest fall back to a paginated grid:

| Entity | Component | Notes |
|--------|-----------|-------|
| Player | `PlayersIndexView.tsx` | Hero (title + tagline, mirrors Voices), 5-stat knowledge row, three themed knowledge highlights (featured player, weekly activity, open ground), `All players (N)` heading with filter chips and sort pill inline, `By team` / `By position` / `By price` chips each toggle a horizontal `FilterDrawer` (multi-select — click chips to add/remove, click again to clear; team chips carry team logos plus a search input; position labels are humanised — SuperCoach `CTW` renders as `Centre / Wing` so wingers aren't hidden; price chips are fixed buckets — `<$300K`, `$300K–$500K`, `$500K–$700K`, `$700K–$900K`, `$900K+`) that filters the grid live with one footer pill per active selection, gapped card grid with 84×84 thumbnails matching `VoiceCard`, low-evidence callout, ask box |
| Voices | `VoicesView.tsx` | Combines `advisor` + `channel` pages |
| Sources | `SourcesView.tsx` | Hero + searchable / sortable `SourceCard` grid (84×84 YouTube thumbnail, YouTube click-out chip, title, voice chip — small logo+name pill linking to `/wiki/channel/<slug>` — claim count + relative time). Voice payload comes from `/api/sources` (joins `Source.channel` and returns `slug`, `name`, `logo_url`); legacy rows without `channel_id` fall back to plain `creator_name` text. |
| Team / Round | `WikiIndexClient.PaginatedGrid` | Generic paginated card grid |

**Per-page detail views.** Most page types render through the generic
`WikiPageClient` (markdown hero + body). Channel pages have a bespoke
`ChannelView.tsx` shell — main column with hero card (logo, title, "Voice"
badge, description, tag pills, platform CTA) and a Latest-episodes panel;
sidebar with About / Coverage / Related-voices cards. The route page fetches
the page payload and a small batch of sibling channels in parallel for the
related-voices sidebar.

Episode rows in the Latest-episodes panel always deep-link internally to
`/wiki/source/[sourceId]` (the source review page — video player + episode timeline
+ transcript + claims). When a source hasn't been transcribed yet,
`/api/sources/{id}` returns the source metadata with empty `claims`/`chunks`/
`speakers`, and the review page renders the video player plus an
"awaiting transcription" placeholder in the Transcript/Claims panel rather
than 404ing. The platform URL (e.g. YouTube) also appears as a small
secondary icon on the right of each row for users who'd rather watch on the
source platform.

The source review page renders an `EpisodeTimeline` strip beneath the video:
filter chips per claim type (with a disabled "Speaker changes" placeholder
chip for diarisation, which lands later), a horizontal bar with click-to-seek
markers per claim coloured by `CLAIM_TYPE_COLORS`, and a live playhead tied to
`currentTime`. Duration is derived from the furthest chunk/claim end-timestamp
since `sources.duration_seconds` isn't on the source detail API yet.

The `TranscriptPanel` to the right of the video is **turn-grouped**: chunks
with the same `speaker_segment_id` collapse into a single block, prefixed with
a click-to-rename speaker label and a `[mm:ss]` click-to-seek timestamp.
Speaker labels are colour-stable across turns (hashed off the label string,
so renames preserve colour). Renaming a label inline issues
`PATCH /api/sources/speakers/{segment_id}` and cascades the new name to every
turn from the same speaker in the document. Within a turn, a chunk with
`paragraph_break=true` (set at extract time when the within-turn pause
exceeds 1.5s) renders as a paragraph break — useful for long monologues.

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
| `GET /api/wiki/pages` | List pages. Filters: `page_type`, `status`, `q`. Cursor pagination. Returns `metadata_json` per page for team/position/price grouping. For channel-backed pages, also bulk-loads `logo_url`, `platform` and `channel_url` from the `channels` table. For player-backed pages, bulk-loads current `team`, `team_short` and `position` from `people_attributes` (`is_current = true`) into `metadata_json` so the Players index can render and filter by team without a per-row stub payload. One extra query per join, regardless of page count. |
| `GET /api/wiki/pages/{slug}` | Full page detail + revisions + `linked_pages` map |
| `GET /api/wiki/pages/{slug}/revisions` | Full revision history |
| `GET /api/wiki/recent-changes` | Recent revisions across all pages |
| `GET /api/wiki/channels/{slug}/episodes` | Latest sources (episodes) for a channel-backed page, ordered by `published_at` desc. Returns title, thumbnail, duration, canonical URL, ingestion status. Powers the "Latest episodes" panel in `ChannelView`. |
| `GET /api/sources` | Every row in `sources`, with `claim_count` and an optional `voice` block (`slug`, `name`, `logo_url`) joined from `channels`. Powers the wiki Sources index and its voice chips. Unprocessed sources have `claim_count=0`; legacy rows without `channel_id` have `voice: null`. |

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
| `services/web/src/app/wiki/PlayersIndexView.tsx` | Bespoke `/wiki?type=player` index — stats, highlights, filterable card grid |
| `services/web/src/app/wiki/VoicesView.tsx` | `/wiki?type=voices` index — advisors + channels |
| `services/web/src/app/wiki/channel/[slug]/ChannelView.tsx` | Bespoke channel detail page — hero card + sidebar (About / Coverage / Related voices) |
| `services/web/src/app/wiki/WikiIndexClient.tsx` | Wiki dashboard + per-entity entry-point routing. The dashboard's `Sources` entity tile synthesises sample avatar chips from the most-recent sources' `voice` blocks (sources don't live in `wiki_pages`, so it can't pull samples from there), each linking to `/wiki/channel/<slug>`. |
| `scripts/data/seed_wiki.py` | One-time seed from existing KB entries |
| `scripts/data/backfill_wiki_team_pages.py` | One-shot backfill of `wiki_pages` rows for every `Team` (gap left by `seed_teams.py`, which only writes to `teams`) |
| `scripts/data/backfill_team_logos_from_parents.py` | Copies `logo_url` from each NRL parent to its NRLW / reserve-grade children. Independent QLD Cup clubs and PNG Chiefs NRL still need hand-curated URLs. |

---

## Related Documents

- [Content pipeline](content-pipeline.md) — sources, cleaning, and the managed agent update flow
- [Page design](page-design.md) — wiki colour palette, typography, component vocabulary
- [LLM Wiki pattern](llm-wiki-pattern.md) — the underlying pattern this wiki is built on
