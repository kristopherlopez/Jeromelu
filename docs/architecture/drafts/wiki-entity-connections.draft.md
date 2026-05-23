---
tags: [area/architecture, subarea/wiki]
status: draft
---

# Wiki Entity Connections (Draft)

> Draft. Last reviewed: 2026-05-12.
>
> Proposes the design for entity-to-entity connections in the wiki — the
> first concrete fill-in of the "HOW THIS CONNECTS" placeholder
> ([page-design.md:133-153](../../pages/wiki/page-design.md)) and the Phase 2
> roadmap item in [overview.md:109-119](../../pages/wiki/overview.md). Circulating
> for reaction before any schema, API, or UI work begins.

---

## The problem

Today the wiki has rich *entity* pages and rich *claim* attribution, but no
first-class concept of an edge between two entities. The only existing
connections are:

| Where | What it expresses | Limitation |
|-------|-------------------|------------|
| `claims.speaker_entity_id` → `claims.subject_entity_id` | "Advisor X said something about player Y" | Bound to a single quote; no edge-level semantics. |
| `quotes.speaker_entity_id` | "Person P spoke in source S" | Person ↔ source, not person ↔ person. |
| `[[slug]]` markdown links inside `wiki_pages.content` | "Page A's prose mentions page B" | Implicit text reference; can't be queried, weighted, or surfaced as a graph. |

So we can answer *"what has SC Playbook said about Cleary?"* but not
*"who is on Cleary's coaching tree?"*, *"which advisors most often agree with
SC Playbook?"*, or *"what teams have Tom Trbojevic played for?"*. The
"HOW THIS CONNECTS" panel on the wiki index is currently a static teaser
graphic precisely because we have nothing to draw.

This doc proposes how to model, populate, and surface these edges.

---

## Three decisions to make

The shape of the system depends on three design choices. For each one I
state the options, the recommended choice, and the trade-off.

### Decision 1 — Where do edges come from?

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **Derived only** | Edges are computed on demand from `claims`, `entity_roles`, and existing FKs. No new table. | No new write path. Always fresh. Cheap to start. | Limited to relationships already implicit in claims. Can't express "X coached Y" unless someone said it in a transcript. Hard to surface in UI without an edge table to query. |
| **First-class table** | A new `wiki_relations` table the agent (and operators) write to. Edges can be derived *or* curated. | Supports both kinds of facts. Queryable, indexable, displayable. Matches the placeholder's intent. | New write path → needs care around dedup, provenance, contradiction. |
| **Hybrid** ★ | First-class `wiki_relations` table, but most rows are agent-derived from claims/role data. Curated edges sit alongside, distinguished by `source`. | Cheap edges where claims already cover it; rich edges where they don't. One query interface for the UI. | Slightly more work upfront than "derived only". |

**Recommendation: hybrid.** Same shape as the existing SCD-2 pattern
([entity-roles.md:181-200](../../concepts/entity-roles.md)) — the table is the
system of record; the derivation pipeline writes most rows; humans (or
specialised agents) write the rest. Provenance lives in `source`.

### Decision 2 — Typed or untyped predicates?

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **Typed (closed vocab)** ★ | A controlled enum: `teammate_of`, `coached_by`, `played_for`, `traded_to`, `rivals_with`, `mentored_by`, `agrees_with`, `contradicts`, `hosts_with`, `covers`, `married_to`, … | Cheap to query, render, and filter. UI can show a typed legend. Agents must commit to a meaning. | Vocab needs governance; adding a new type is a migration-grade decision. |
| **Untyped (free-form predicate string)** | Any string predicate the agent invents. | Maximum expressivity. | UI can't render unknown predicates well; query/filter degenerates; vocab drift. |
| **Both** | Typed enum + a free-form `note` field for nuance. | Best of both. | Slightly more schema. |

**Recommendation: typed enum + a free-form `note`.** Start with ~10 types
covering the obvious cases. Add new types via migration when a need is
proven by ≥3 unmodelled edges in the wild — same discipline we use for
`entity_type`. The `note` field absorbs nuance ("centre-pairing for the
2018-19 seasons") without polluting the predicate space.

Initial vocab proposal (revise before merge):

| Type | Domain | Direction |
|------|--------|-----------|
| `played_for` | player → team | directed, temporal |
| `coached` | coach → team \| player | directed, temporal |
| `coached_by` | player → coach | directed, temporal (inverse view) |
| `teammate_of` | player ↔ player | symmetric, temporal |
| `traded_to` | player → team | directed, temporal (one-shot) |
| `mentored_by` | person → person | directed, temporal |
| `rivals_with` | person ↔ person \| team ↔ team | symmetric, soft |
| `hosts_with` | advisor ↔ advisor | symmetric, temporal |
| `publishes_on` | advisor → channel | directed, temporal |
| `agrees_with` | advisor → advisor | directed, derived from claim co-occurrence |
| `contradicts` | advisor → advisor | directed, derived from claim co-occurrence |
| `covers` | channel → entity | directed, derived from claim volume |

`agrees_with` / `contradicts` / `covers` are explicitly **derived** —
populated by the analytics pass over `claims`, not by curation. The others
are mostly curated (or extracted from prose by Archivist).

### Decision 3 — Directionality and temporality

Most NRL relationships are time-bounded. Tom Trbojevic *played for Manly
2015–present*; Bellamy *coached Storm 2003–present*; Andrew Johns *played
for Newcastle 1995–2007*. Three options:

| Option | Description |
|--------|-------------|
| **No temporality** | Edges are evergreen. Lose tenure information. |
| **`effective_from` / `effective_to`** ★ | Same SCD-2 shape as `entity_roles` and `player_attributes`. Open `effective_to = NULL` means current. |
| **Versioned snapshots** | Materialised "as of round N" graph snapshots. |

**Recommendation: option 2 (SCD-2).** It matches the project convention
documented in [entity-roles.md:181-200](../../concepts/entity-roles.md). The
*"three SCD-2 tables triggers consolidation"* rule applies — `wiki_relations`
would be the third, so we either consolidate at that point or accept
that this is a separate, edge-shaped concern that doesn't fit into a
generic `entity_affiliations` table cleanly. Worth flagging now rather than
discovering later.

For directionality: store edges directed (`a_id`, `b_id`, `relation_type`).
Symmetric types are stored once; the read API canonicalises by
`(LEAST(a_id, b_id), GREATEST(a_id, b_id))` for symmetric types and
returns both perspectives in the response.

---

## Proposed schema

```sql
-- packages/db/migrations/0NN_wiki_relations.sql

CREATE TYPE wiki_relation_type AS ENUM (
    'played_for', 'coached', 'coached_by', 'teammate_of',
    'traded_to', 'mentored_by', 'rivals_with',
    'hosts_with', 'publishes_on',
    'agrees_with', 'contradicts', 'covers'
);

CREATE TABLE wiki_relations (
    relation_id    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    a_entity_id    UUID NOT NULL REFERENCES entities(entity_id),
    b_entity_id    UUID NOT NULL REFERENCES entities(entity_id),
    relation_type  wiki_relation_type NOT NULL,
    note           TEXT,
    weight         REAL,                  -- for derived edges (0..1)
    evidence_claim_ids UUID[] DEFAULT '{}',
    effective_from DATE,
    effective_to   DATE,                  -- NULL = current
    is_current     BOOLEAN GENERATED ALWAYS AS (effective_to IS NULL) STORED,
    source         TEXT NOT NULL,         -- 'archivist', 'analyst/derived', 'operator/<name>', 'seed/...'
    metadata_json  JSONB DEFAULT '{}',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (a_entity_id <> b_entity_id)
);

-- one open edge of each (a, b, type) pair at a time
CREATE UNIQUE INDEX uq_wiki_relations_open
  ON wiki_relations(a_entity_id, b_entity_id, relation_type)
  WHERE effective_to IS NULL;

CREATE INDEX idx_wiki_relations_a   ON wiki_relations(a_entity_id);
CREATE INDEX idx_wiki_relations_b   ON wiki_relations(b_entity_id);
CREATE INDEX idx_wiki_relations_type ON wiki_relations(relation_type);
```

Notes:

- `note` carries nuance the predicate can't ("centres at Manly 2018-19").
- `weight` is for derived edges (e.g. `agrees_with` = 0.84 means SC Playbook
  agreed with NRL Brothers on 84% of overlapping claims). For curated edges,
  weight is `NULL`.
- `evidence_claim_ids` lets the UI surface "why does this edge exist?" by
  jumping straight to the supporting claims — same pattern as
  `predictions.evidence_claim_ids` ([001_initial_schema.sql:89](../../../packages/db/migrations/001_initial_schema.sql)).
- `source` distinguishes the four populator paths described below.
- `is_current` is generated so indexes/UI can filter without recomputing.

---

## How edges get created

Four populator paths, each writing to the same table with a distinct
`source` value:

```
                                    ┌──────────────┐
   1. seed scripts ───────────────► │              │
                                    │              │
   2. Archivist (per page update)─► │ wiki_        │
                                    │ relations    │
   3. Analyst (claim-derived) ────► │              │
                                    │              │
   4. operator (manual override) ─► │              │
                                    └──────────────┘
                                            │
                                            ▼
                                    GET /api/wiki/relations
                                            │
                                            ▼
                                  Wiki index graph + entity
                                  page "Connections" panel
```

| Path | Trigger | Edge types it writes | Source value |
|------|---------|----------------------|--------------|
| **Seed** | One-time backfill from `entity_roles` and `player_attributes` | `played_for`, `coached`, `publishes_on` | `seed/from-entity-roles` |
| **Archivist** | Wiki update session ([content-pipeline.md](../../pages/wiki/content-pipeline.md)) when prose mentions a relation | All curated types | `archivist` |
| **Analyst** | Periodic batch over `claims` | `agrees_with`, `contradicts`, `covers` | `analyst/derived` |
| **Operator** | Manual API or admin UI for corrections | Any | `operator/<name>` |

The Archivist already rewrites wiki pages from claims and stats — extracting
relations is a small extension: when prose says "Tom Trbojevic plays for
Manly", the agent calls `upsert_wiki_relation(player=tom-trbojevic,
team=manly-sea-eagles, type=played_for)` instead of (or in addition to)
just writing the prose. The MCP server in
[content-pipeline.md:54-68](../../pages/wiki/content-pipeline.md) gains
`upsert_wiki_relation` and `close_wiki_relation` operations.

The derived pass (Analyst) is a pure read over `claims`: for each pair of
advisors with overlapping subjects in a window, compute the proportion of
claims with matching `polarity` → write a single `agrees_with` row with the
weight. Re-run weekly; supersede prior open rows.

---

## How edges surface in the UI

Three concrete surfaces. All read from `GET /api/wiki/relations`.

### 1. Index page — "How this connects" graph

Replaces the static teaser at
[page-design.md:133-153](../../pages/wiki/page-design.md). The component
fetches the top-N highest-weight edges (tunable, e.g. ~100) and renders
them as an interactive force-directed graph. Same colour palette as the
rest of the wiki (warm parchment + accent). Click a node → entity page.

### 2. Entity page — "Connections" panel

Each entity page gains a sidebar (or new section) called **Connections**,
grouped by `relation_type`:

```
CONNECTIONS
  Teams played for     → Manly Sea Eagles (2015–)
  Teammates            → Daly Cherry-Evans, Jake Trbojevic, …
  Coached by           → Anthony Seibold (2024–), Des Hasler (2018–22)
  Most agreed with     → SC Playbook (84%), NRL Physio (76%)
  Most contradicted by → KingOfSC (62%)
```

Each row is a `[[slug]]` link; the bracketed metadata renders from the
edge's `effective_from`/`to` and `weight`/`note`. This is the *first*
case where wiki-link rendering needs structured data alongside the link
text — worth deciding whether the panel is markdown-driven (Archivist
writes the whole panel) or component-driven (frontend queries
`/api/wiki/relations?entity_id=...` and renders the panel itself).
**Recommendation: component-driven**, so the panel stays in sync with
the table without an Archivist round-trip.

### 3. New API endpoint

| Endpoint | Purpose |
|----------|---------|
| `GET /api/wiki/relations` | Filters: `entity_id`, `relation_type`, `current_only`, `min_weight`. Returns edges with both entity stubs (slug, title, page_type) for cheap rendering. |
| `GET /api/wiki/relations/graph` | Pre-shaped for the index graph: top-N by weight, deduped, with positions hint. |
| `POST /api/wiki/relations` | Operator-only. Upsert. |
| `PATCH /api/wiki/relations/{id}` | Operator-only. Close, re-weight, edit note. |

---

## Phasing

A staged rollout that earns each phase from the prior one's data:

| Phase | Scope | Ships |
|-------|-------|-------|
| **0 — Schema + seed** | Migration; backfill from `entity_roles` and `player_attributes`; backfill `publishes_on` from `channels` host data | Table populated with structural edges; no UI yet |
| **1 — Read API + entity panel** | `GET /api/wiki/relations`; "Connections" sidebar on player and team pages | Users see real connections on entity pages |
| **2 — Derived edges** | Analyst batch for `agrees_with`/`contradicts`/`covers`; weekly cron | Voices index gains "Most agreed with" rows |
| **3 — Index graph** | `GET /api/wiki/relations/graph`; replace the static teaser | The placeholder finally has data behind it |
| **4 — Curation surface** | `POST`/`PATCH` endpoints; minimal admin form for corrections | Operators can fix bad edges without code |

Phases 0–1 are the smallest useful unit: structural edges on entity pages.
Phase 2 onward depends on having a meaningful claim corpus per advisor,
which is currently thin pre-diarisation.

---

## Open questions

1. **Symmetric storage.** Is canonicalising `(LEAST, GREATEST)` for symmetric
   types worth the read-side complexity, or simpler to write both rows and
   accept the duplication?
2. **Three-SCD-table consolidation.** Adding `wiki_relations` makes three
   SCD-2 tables (`entity_roles`, `player_attributes`, `wiki_relations`) —
   the trigger to "revisit and consider unifying"
   ([entity-roles.md:189-198](../../concepts/entity-roles.md)). I think
   `wiki_relations` is genuinely different shape (two FKs, not one) and
   shouldn't be folded in — but worth deciding before migrating.
3. **Edge-derived from prose vs. structured fields.** Should `played_for`
   be sourced from `player_attributes.team` (already SCD-2, authoritative)
   or from `wiki_relations`, or both? If both, which wins on conflict?
   Probably: `player_attributes` is the source of truth and the seed
   populator just mirrors it into `wiki_relations` for graph queries.
4. **Contradiction handling for derived edges.** If two consecutive
   Analyst runs disagree on `agrees_with` weight (one week 0.82, next 0.74),
   do we close the prior and open a new row (full SCD-2), or just `UPDATE`
   in place? In-place loses history; SCD-2 is correct but noisy at weekly
   cadence. Lean toward: in-place updates for derived, SCD-2 for curated.
5. **Privacy of `metadata_json`.** Curated edges may capture sensitive
   context ("personal fallout from the Roosters move"). Default to public
   like the rest of the wiki, or gate `metadata_json` to operator view?
6. **Performance ceiling.** The graph view will eventually want the *whole*
   graph, not top-N. Postgres can handle 10k–100k edges fine; beyond that
   we'd need a graph store. Out of scope for V1, but flag the ceiling.

---

## Documentation Updates

If this draft is accepted, the following docs need updates as part of the
implementing changeset (per CLAUDE.md documentation discipline):

| Doc | Change |
|-----|--------|
| [`docs/pages/wiki/overview.md`](../../pages/wiki/overview.md) | Add `wiki_relations` to the schema section; add the new API endpoints; remove `wiki_relations`-as-future-work from Phase 2 (it becomes Phase 1.5). |
| [`docs/pages/wiki/page-design.md`](../../pages/wiki/page-design.md) | Update the "HOW THIS CONNECTS" notes to describe the live graph; add the entity-page "Connections" panel layout. |
| [`docs/pages/wiki/content-pipeline.md`](../../pages/wiki/content-pipeline.md) | Add `upsert_wiki_relation` / `close_wiki_relation` to the MCP operations table; describe the Archivist responsibility for relation extraction. |
| [`docs/concepts/entity-roles.md`](../../concepts/entity-roles.md) | Add a section noting `wiki_relations` as the third SCD-2 table and the consolidation decision in Open Question 2. |
| [`docs/architecture/01-information-architecture.md`](../01-information-architecture.md) | Add `wiki_relations` to the data-model overview. |
| [`docs/agents/crew/analyst.md`](../../agents/crew/analyst.md) (and `archivist.md` if it exists) | Add the relation-derivation / relation-extraction responsibilities. |
| New: `packages/db/migrations/0NN_wiki_relations.sql` | The migration itself. |
| New: `scripts/data/seed_wiki_relations.py` | Backfill from `entity_roles`, `player_attributes`, and any seeded host data. |

---

## Drafting notes (delete before merge)

This is the first concrete proposal for entity-to-entity edges. Written in
response to the observation that the wiki has rich entities but no edges,
and that the "HOW THIS CONNECTS" panel is a placeholder for a
`wiki_relations` table that has never been designed.

The recommendations above are biased toward the smallest-thing-that-could-
possibly-work that still leaves room for the graph view, derived edges,
and operator curation. If we don't believe in derived edges yet (Phase 2),
the schema and the seed/Archivist paths still earn their keep on their own.

The biggest open question I'm not confident about is **#3 — `played_for`
provenance**. If `player_attributes` is already the source of truth for
"current team", duplicating into `wiki_relations` is a smell. Two paths:
(a) the seed populator continuously mirrors, and `wiki_relations` is the
unified read surface; (b) the read API JOINs `player_attributes` and
`entity_roles` into a unified relations view, and `wiki_relations` only
stores edges that *can't* be derived from existing tables. Path (b) is
purer; path (a) is simpler. Worth a decision before migration.
