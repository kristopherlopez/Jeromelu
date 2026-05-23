---
tags: [area/pages, subarea/wiki]
---

# Wiki Content Pipeline

Status: **Design — not yet implemented**

This doc covers how the **Archivist** updates wiki pages from the structured outputs of the source pipeline. The Archivist is a Claude Managed Agent; the role spec lives in [`docs/agents/crew/archivist.md`](../../agents/crew/archivist.md), this doc covers the runtime. For the source system itself (originals, cleaning, patterns, attribution) see [`docs/sources/`](../../sources/README.md).

---

## Context

Sources → cleaning → claims + stats + team lists is the upstream pipeline. This doc starts where that ends: the Archivist reads the structured outputs via an MCP server, decides what has changed, and rewrites wiki page sections.

The Archivist doesn't process raw transcripts — it consumes already-extracted, verified outputs.

```
   Source pipeline output            Wiki
   (owned by docs/sources/)          (this doc)
   ────────────────────             ────

   claims ────────────────┐
   player_rounds ─────────┤
   teamlists ─────────────┼──→ [Archivist] ──→ wiki_pages
   entities ──────────────┤         ↑               │
   KB entries (optional) ─┘     MCP Server     wiki_revisions
                                (reads DB)          │
                                                    ↓
                                               Activity Feed
```

---

## Wiki Update Architecture

### The Archivist

The Archivist — implemented as a Claude Managed Agent — handles all wiki page updates. It is defined once and triggered per update session. For the role spec (responsibilities, principles, page lifecycle, hand-off contract) see [`docs/agents/crew/archivist.md`](../../agents/crew/archivist.md).

**Agent definition:**
- **Model:** claude-sonnet-4-6 (cost-effective for structured rewrites)
- **System prompt:** Wiki editor instructions — tone, section conventions, wiki-link format, revision logging rules
- **Tools:** `agent_toolset_20260401` (bash, file I/O) + `mcp_toolset` (database access)
- **MCP server:** Custom server exposing read/write operations on the Jaromelu database

**Environment:**
- Python packages for any data processing
- Networking restricted to the MCP server

### MCP Server Operations

The agent interacts with the database exclusively through the MCP server. Required operations:

| Operation | Purpose |
|-----------|---------|
| `get_wiki_page(slug)` | Read current page content, metadata, status |
| `list_wiki_pages(filters)` | Find pages by type, status, entity |
| `update_wiki_page(slug, content, summary)` | Write updated content + create revision |
| `get_claims(filters)` | Query claims by entity, round, source, date range |
| `get_player_stats(entity_id, round)` | Player round stats (score, price, BE, PPM) |
| `get_team_list(team_slug, round)` | Current team list for a round |
| `get_entity(slug)` | Entity metadata (name, type, aliases) |
| `get_kb_entries(filters)` | Pre-synthesised KB summaries (optional context) |
| `search_wiki_pages(query)` | Find related pages for cross-linking |

The `update_wiki_page` operation atomically updates `wiki_pages.content` and inserts a `wiki_revisions` record with `source_trigger`, `section_heading`, `summary`, and optional `source_id`.

### Update Triggers

| Trigger | What fires it | What happens |
|---------|---------------|--------------|
| **New claims uploaded** | `/upload-transcript` completes | Session created for affected player + advisor pages |
| **Post-round stats** | Stats fetcher writes PlayerRound data | Session created for affected player + team + round pages |
| **Team lists published** | Team list fetcher writes new round data | Session created for team + round pages |
| **Manual** | Operator triggers via API or skill | Session created for specified pages |

> **Open question:** Should each trigger create one session per affected page, or one session that updates a batch of related pages? Batching is cheaper ($0.08/hr per session) and lets the Archivist cross-reference, but increases blast radius if something goes wrong.

### Session Flow

When a session is triggered:

1. **Scope** — the session receives a message specifying which pages to update and why (e.g. "New claims from SC Playbook Round 8 episode. Update player pages for: tom-trbojevic, nathan-cleary, ...").

2. **Read current state** — the Archivist reads the current wiki page content via MCP, plus relevant claims, stats, and team list data.

3. **Decide what changed** — the Archivist compares new data against existing page content. If nothing meaningful changed, it skips the page (per the [skip threshold principle](../../agents/crew/archivist.md#knowledge-organisation-principles)).

4. **Rewrite sections** — the Archivist rewrites only the affected sections (e.g. `## Expert Opinions`, `## Price Analysis`), preserving sections it didn't touch. It maintains `[[slug]]` wiki-links and follows the page's existing structure.

5. **Log revision** — for each page updated, the Archivist calls `update_wiki_page` which creates a `wiki_revisions` record with:
   - `section_heading` — which section was changed
   - `summary` — human-readable description (e.g. "Updated Expert Opinions with SC Playbook Round 8 claims")
   - `source_trigger` — what caused the update (e.g. `archivist/claims-upload`)
   - `source_id` — FK to the source that triggered it, if applicable

6. **Report** — the session returns a summary of what was updated, skipped, and any issues.

---

## Page Section Conventions

Each page type has a defined section structure. The Archivist updates specific sections based on the upstream data source.

### Player Pages

| Section | Updated by | Source data |
|---------|-----------|-------------|
| `## Overview` | Archivist (infrequent) | Entity metadata, position, team |
| `## Current Form` | Archivist (post-round) | Recent PlayerRound stats, form trajectory |
| `## Price Analysis` | Archivist (post-round) | Price, breakeven, ownership trends |
| `## Expert Opinions` | Archivist (post-claims) | Recent claims from advisors, consensus direction |
| `## Selection History` | Archivist (weekly) | Team list appearances, jersey numbers |

### Team Pages

| Section | Updated by | Source data |
|---------|-----------|-------------|
| `## Overview` | Archivist (infrequent) | Team metadata |
| `## Current Squad` | Archivist (weekly) | Team list data |
| `## Recent Results` | Archivist (post-round) | Match stats |
| `## Key Players` | Archivist (post-round) | Top SC scorers, form players |

### Channel Pages

Channel pages describe the **outlet** (SC Playbook YouTube, NRL Physio Twitter).
They are seeded from the `channels` table and updated as new sources are ingested
through that channel.

| Section | Updated by | Source data |
|---------|-----------|-------------|
| `## About` | Archivist (infrequent) | `channels.description`, platform metadata |
| `## Recent Sources` | Archivist (per-source) | Last ~10 `sources` rows for this channel |
| `## Coverage` | Archivist (infrequent) | `channels.tags` |
| `## Hosts` | Archivist (when advisor pages land) | Linked advisor entities (deferred until Phase 2 speaker diarisation) |
| `## Track Record` | Archivist (post-round, Phase 3) | Channel-level prediction accuracy |

### Advisor Pages (deferred)

Advisor pages describe the **person/voice** (Tim Williams, Brien Seeney). The
schema and route exist but no advisor pages are seeded yet — they appear as
the Archivist identifies named voices with confidence (post speaker diarisation).

| Section | Updated by | Source data |
|---------|-----------|-------------|
| `## Overview` | Archivist (infrequent) | Person bio, role history (`entity_roles`) |
| `## Channels` | Archivist (when host data exists) | Channels this person publishes through |
| `## Recent Calls` | Archivist (post-claims) | Latest claims where `quotes.speaker_entity_id` matches |
| `## Track Record` | Archivist (post-round, Phase 3) | Person-level accuracy across all their channels |

### Round Pages

| Section | Updated by | Source data |
|---------|-----------|-------------|
| `## Overview` | Archivist (pre-round) | Fixtures, dates, venues |
| `## Team Lists` | Archivist (weekly) | Team list data per match |
| `## Key Talking Points` | Archivist (post-claims) | Notable claims, consensus shifts |
| `## Results` | Archivist (post-round) | Match stats, scores, top performers |

---

## Revision Tracking

Every wiki update creates a `wiki_revisions` record. The `source_trigger` field categorises what caused the update:

| source_trigger | Meaning |
|----------------|---------|
| `archivist/claims-upload` | New claims from a processed transcript |
| `archivist/post-round-stats` | Player/match stats for a completed round |
| `archivist/team-lists` | Weekly team list update |
| `archivist/manual` | Operator-triggered update |
| `seed_wiki.py` | Initial seeding (historical) |

Revisions power the activity feed (`GET /api/wiki/recent-changes`) and per-page revision history.

---

## Role Transitions

When the Archivist encounters evidence that a person's role has changed (e.g. a
player has retired and started commentating), it should update `entity_roles`
rather than mutating the entity row:

1. Close the existing primary role: `UPDATE entity_roles SET effective_to = <date> WHERE entity_id = X AND is_primary AND effective_to IS NULL`.
2. Insert the new primary role: `INSERT INTO entity_roles ... is_primary = TRUE, effective_to = NULL`.
3. Sync the denorm: `UPDATE entities SET entity_type = '<new role>' WHERE entity_id = X`.

For concurrent roles (Michael Ennis: coach + commentator), insert the secondary
role with `is_primary = FALSE` and the same open `effective_to`. Only the primary
role drives the wiki page route.

Transition detection is slow-moving and operator-confirmed by default. See
[Entity roles](../../concepts/entity-roles.md) for examples.

---

## Open Questions

1. **Session granularity** — one session per page, per batch of related pages, or one big session per trigger event?
2. **Automation level** — should post-round stats and team list updates trigger wiki sessions automatically, or remain operator-triggered?
3. **KB entry role** — should the Archivist read KB entries as pre-digested context, or work directly from raw claims/stats? KB adds a synthesis layer but also an indirection.
4. **Conflict handling** — if two sources give contradictory claims about the same player, how should the Archivist handle it in the wiki prose? Flag both? Weight by advisor accuracy?
5. ~~**Page creation**~~ — *Resolved (2026-05-12).* The Archivist creates stub pages proactively when prose links to an unstubbed entity. See [archivist.md → Page lifecycle](../../agents/crew/archivist.md#page-lifecycle).
6. **MCP server location** — hosted alongside the API (as additional FastMCP routes), or as a separate service?

---

## Key Files

| File | Purpose |
|------|---------|
| [`docs/pages/wiki/overview.md`](overview.md) | Wiki feature spec (schema, API, content format) |
| [`docs/pages/wiki/llm-wiki-pattern.md`](llm-wiki-pattern.md) | LLM Wiki pattern (conceptual basis) |
| [`docs/sources/`](../../sources/README.md) | Source pipeline — originals, cleaning, attribution |
| [`packages/db/migrations/015_wiki.sql`](../../../packages/db/migrations/015_wiki.sql) | Wiki schema |

---

## Related Documents

- [Wiki Feature](overview.md) — schema, API, frontend
- [Source system](../../sources/README.md) — upstream of this pipeline
- [Information Architecture](../../architecture/01-information-architecture.md) — data model
- [LLM Wiki Pattern](llm-wiki-pattern.md) — conceptual foundation
