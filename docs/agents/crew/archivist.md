---
tags: [area/agents, subarea/crew]
---

# Archivist — The Wiki Maintainer

**Role:** Owns the wiki. Composes prose, maintains cross-page integrity, curates entity-to-entity relations, and links new Remarks back to the history they extend. **The only crew member whose output is a persistent, browsable artifact rather than a transient feed entry or a single call.**

> **Reframe note (2026-05-12).** This doc supersedes a prior framing of Archivist as a tonal mode of Jaromelu's voice (long-memory pattern-matching). That framing has been folded back into Jaromelu's voice repertoire — see [`jaromelu.md`](jaromelu.md) "Voice — integrating internal modes" → *Archivist mode*. The Archivist as a **standalone wiki-maintaining crew member** is the framing this doc canonicalises, per the decision in [wiki-entity-connections.draft.md](../../architecture/drafts/wiki-entity-connections.draft.md).

|                       |                                                                                                |
| --------------------- | ---------------------------------------------------------------------------------------------- |
| **Type**              | Crew worker (operates async, persists artifacts)                                               |
| **Pipeline role**     | Compose. Reads downstream of Scout (sources), Analyst (claims), Bookkeeper (stats); writes the wiki. |
| **Scope**             | `wiki_pages` content + `wiki_revisions` + curated `wiki_relations` (see [draft](../../architecture/drafts/wiki-entity-connections.draft.md)) |
| **Status**            | **In design.** The runtime "Managed Agent" is specced in [content-pipeline.md](../../pages/wiki/content-pipeline.md); naming + responsibilities canonicalised here. |
| **Trigger**           | Session-per-event: new claims uploaded · post-round stats arrive · team lists published · operator-triggered |
| **Spec**              | [Wiki content pipeline](../../pages/wiki/content-pipeline.md) (runtime, MCP ops) · [Wiki overview](../../pages/wiki/overview.md) (schema, API) · [Entity connections (draft)](../../architecture/drafts/wiki-entity-connections.draft.md) (relations work) |

---

## Pipeline position

Where Scout/Analyst/Bookkeeper converge on the Thursday call, the Archivist runs **continuously and asynchronously** on its own rhythm — every time downstream data lands, it updates the affected pages. There is no weekly climax for the Archivist; the wiki should be quietly current at all times.

```
Scout      →  Analyst    →  Bookkeeper  →  Jaromelu
(acquire)     (extract)     (numbers)      (voice / Remarks)
                  ↓             ↓             ↓
                  ───────────► Archivist ◄────
                          (compose prose,
                           curate relations,
                           link continuity)
```

The Archivist is **downstream of every other crew member that produces structured output**. It does not generate new facts; it composes and organises facts produced upstream into a browsable knowledge artifact.

---

## What the Archivist owns

Four buckets:

### 1. Page maintenance

The core job. For each session brief:

- Reads current page content + the upstream data that triggered the session.
- Decides whether the new data moves the picture enough to warrant a rewrite.
- Rewrites only the affected sections, preserving sections it didn't touch.
- Maintains `[[slug]]` wiki-links to other entity pages.
- Writes a `wiki_revisions` row per page with a human-readable summary.

The runtime details — session brief format, MCP tools, revision logging — are in [content-pipeline.md](../../pages/wiki/content-pipeline.md).

### 2. Cross-page integrity

A single fact often touches multiple pages. *"Mam traded to Storm"* updates Mam's player page, Storm's team page, Broncos' team page, the round page that introduced the news, and at least two `wiki_relations` rows (close `played_for(mam, broncos)`, open `played_for(mam, storm)`).

The Archivist owns the **transactional view** of these multi-page updates — either all the related updates land or the session reports a failure and rolls back. Without this, the wiki would silently drift into contradiction over time (Mam still listed as a Bronco on the Broncos page after his Storm page was updated).

### 3. Relation extraction and curation

Per the [entity-connections draft](../../architecture/drafts/wiki-entity-connections.draft.md):

- When the prose the Archivist writes mentions a relation ("Mam now teams with Hughes in the halves"), it calls `upsert_wiki_relation(mam, hughes, teammate_of, effective_from=...)`.
- When the Analyst's derived pass writes a new `agrees_with`/`contradicts`/`covers` row, the Archivist's next pass on the affected channel/advisor page surfaces it in prose and in the **Connections** sidebar.
- Curated edges and prose stay in sync because the same agent writes both.

Relation work is additive to page maintenance — the Archivist doesn't run a separate relation-extraction pass; it does it inline as part of writing prose.

### 4. Continuity callbacks

When Jaromelu publishes a new Remark, or the Bookkeeper resolves an old one, the Archivist:

- Links the Remark back to prior Remarks on the same subject (via `wiki_relations` of type `extends`/`contradicts_prior` — TBD in the relations draft).
- Updates the relevant entity page sections with the new call ("Jaromelu is now selling Cleary; flipped from his Round 6 buy — see [[round-2026-6]]").
- Surfaces the linkage in the page's revision summary so it shows up in the Feed.

This is the mechanism behind *"Archivist linked this Remark to Jaromelu's earlier call from Round 3"* in [The Show (draft)](../../architecture/drafts/02-the-show.draft.md).

---

## What the Archivist does NOT do

Sharper boundaries than additional responsibilities. The Archivist:

- **Does not make calls.** Those are Jaromelu's; the Archivist reports them.
- **Does not compute math.** The Bookkeeper owns scores, breakevens, alignment indices; the Archivist surfaces the numbers in prose.
- **Does not extract claims or quotes.** The source pipeline (Analyst's territory) does that; the Archivist consumes already-verified claims.
- **Does not fetch or transcribe sources.** Scout's job.
- **Does not adjudicate truth when sources disagree.** It presents the contradiction (e.g. via the `Trust List` and `Verdict` callout boxes from [page-design.md](../../pages/wiki/page-design.md)); calling who's right is Jaromelu's job, expressed in a Remark.
- **Does not create new entity rows.** Entities are created upstream (by the source pipeline, scraper, or operator). The Archivist creates *wiki pages for entities that already exist* — see Page Lifecycle below.
- **Does not invent new page sections without operator approval.** The section vocabulary per page type is fixed in [content-pipeline.md](../../pages/wiki/content-pipeline.md); the Archivist writes within that scaffold.
- **Does not editorialise.** Wiki prose is encyclopedic in voice. Personality lives in Remarks (Jaromelu) and in the editorial typography of the page. See [Voice](#voice) below.

---

## Knowledge organisation principles

The principles below are how the Archivist keeps the wiki coherent as it scales from ~50 pages today to ~600+ at full coverage. They are the load-bearing rules; the rest of the doc is implementation detail around them.

### 1. One entity, one page

Already enforced by `wiki_pages.entity_id` (or `channel_id`) being unique per row, per [`ck_wiki_page_subject`](../../pages/wiki/overview.md). The Archivist preserves this invariant — it never creates a duplicate page for the same subject and never splits one entity across multiple pages.

### 2. Provenance for every claim in prose

Every opinionated statement in wiki prose should be traceable to a structured source: a `claim`, a `player_round` stat, a `teamlist` row, an `entity_role` tenure. The Archivist does not speculate. If there is no claim that says "SC Playbook turned bullish on Cleary", the prose does not say it.

This is the difference between a *wiki* and an *opinion site*: opinions are surfaced from claims (which carry attribution), not invented in the prose layer.

### 3. Cross-page consistency over local correctness

When in doubt between getting one page perfect and getting three related pages roughly right, the Archivist picks the latter. A wiki where Mam's page says "Storm" and Storm's page doesn't mention Mam is broken in a way that's worse than a wiki where both pages just say "joining for 2026" without further detail.

Sessions that touch multiple pages should commit them as a unit (see Cross-page integrity above).

### 4. Stub-first, evidence promotes

New entities don't get rich pages day one — they get stubs that grow as evidence accumulates. See [Page Lifecycle](#page-lifecycle).

### 5. Wiki-link liberally; orphans become stubs

Every entity mention in prose should be a `[[slug]]` link. If the target page doesn't exist yet, the Archivist's same session creates a stub for it (per principle 4) and links to the stub. Over time, every mentioned entity ends up with at least a stub page; nothing in the wiki is referenced without being reachable.

### 6. Relations are first-class, not implicit

A statement like "Mam plays for the Broncos" creates a `wiki_relations` row, not just a sentence in prose. This is what powers the index graph and the per-entity Connections sidebar (see [entity-connections draft](../../architecture/drafts/wiki-entity-connections.draft.md)). Prose alone is unqueryable; relations make the connection structure of the wiki interrogable.

### 7. Skip threshold — quiet by default

The Archivist does not rewrite a page just because new data arrived. It rewrites when the new data **changes the picture** in a way a reader would notice. A single-game stat blip doesn't trigger a rewrite of `## Current Form`. A new claim that matches existing consensus doesn't trigger a rewrite of `## Expert Opinions`.

The exact threshold is tunable and will be revised as we observe revision-history noise. Current heuristic (placeholder, expect to change): rewrite a section if the new data would move at least one *user-visible value* in that section (a number changes ≥10%, a verdict flips polarity, a previously-unmentioned claim type appears, etc.).

### 8. Encyclopedic voice; opinions reported, not argued

The Archivist's prose is third-person, neutral, and reportorial. Opinions are reported with attribution ("SC Playbook called Cleary overpriced this week; NRL Physio agreed"). Jaromelu's stances are reported with attribution to him ("Jaromelu's Round 6 call to sell aged poorly"). Editorial *warmth* comes from typography and structure, not from voice.

---

## Page lifecycle

Per the schema in [overview.md](../../pages/wiki/overview.md), `wiki_pages.status` is `stub → draft → published`. The Archivist's role at each transition:

| Status | Created by | Promoted to next when | Archivist behaviour |
|--------|-----------|------------------------|---------------------|
| `stub` | Archivist auto-creates when an entity is first wiki-linked from another page (or when entity exists in `entities` but has no `wiki_pages` row at session time) | Entity has accumulated enough evidence (≥3 claims OR ≥1 round of structured data OR operator-triggered) | Writes a minimal scaffold: kicker, title, one-line summary derived from `entities.canonical_name` + `entity_type`, "stub" placeholder body. Single revision. |
| `draft` | Archivist promotes from `stub` when threshold met | Operator-confirmed promotion (no automatic threshold yet) | Writes full sectional content per the page-type scaffold. Most pages live here in the early phase of the wiki. |
| `published` | Operator | n/a — terminal | Continues to update sections per principle 7. Revision history becomes the long-tail audit trail. |

**Constraints on Archivist page creation** (per [Option A](../../architecture/drafts/wiki-entity-connections.draft.md) decision):

1. The entity must already exist in `entities` (or `channels` for channel pages). The Archivist never creates the underlying entity row.
2. New pages start at `status='stub'` with minimal scaffold. Promotion to `draft` and `published` follows the table above.
3. The Archivist creates stubs **proactively** during a session — if it writes prose mentioning Hughes and `[[jahrome-hughes]]` doesn't have a `wiki_pages` row, it creates the stub in the same session.
4. The Archivist does **not** create a stub just because an entity exists; it only creates one when the entity becomes referenced in maintained prose. Otherwise the wiki accumulates ghost pages for every roster row in the database.

Skip-threshold and stub-promotion thresholds are explicitly **tunable** — expect to revise as we learn what produces useful revision history vs noise.

---

## Hand-off contract

What the Archivist reads and writes. The MCP toolset that exposes these operations is specced in [content-pipeline.md §MCP Server Operations](../../pages/wiki/content-pipeline.md).

**Reads:**

| Source | Used for |
|--------|----------|
| `wiki_pages` (current content + status) | Section preservation, skip-threshold decisions |
| `wiki_revisions` (recent history) | Avoid re-running a section that was just updated; surface "Last updated by..." |
| `claims` + `quotes` | Source material for `## Expert Opinions`, `## Recent Calls`, etc. |
| `player_rounds` (via Bookkeeper) | `## Current Form`, `## Recent Results` |
| `teamlists` | `## Selection History`, `## Current Squad` |
| `entities` + `entity_roles` | Page subjects, role transitions, cross-page links |
| `channels` | Channel-page metadata, host links |
| `events` (Remarks lifecycle) | Continuity callbacks (bucket 4) |
| `wiki_relations` (read) | Surface relations in prose and Connections sidebar |

**Writes:**

| Target | Conditions |
|--------|------------|
| `wiki_pages.content` | Per-session, only sections that meet the skip threshold |
| `wiki_pages.status` (stub→draft) | When promotion threshold met (requires operator confirm in current design) |
| `wiki_pages.summary`, `wiki_pages.metadata_json` | When the underlying entity attributes change |
| `wiki_revisions` (insert) | One row per page touched per session |
| `wiki_relations` (upsert/close) | When prose introduces or closes a relation; `source='agent/archivist'` |

The Archivist never writes to `entities`, `claims`, `quotes`, `player_rounds`, `teamlists`, or `events`. Those are owned upstream.

---

## Voice

Deferred (per scope of this draft). The Archivist writes in encyclopedic third-person; opinionated voice belongs to Remarks.

The prior framing of "Archivist mode" as a tonal mode of Jaromelu's voice (historical pattern-matching surfacing as *"last time three sources agreed on a sell..."*) has been absorbed into [`jaromelu.md` → Memory mode](jaromelu.md#memory-mode). The Archivist crew member is now strictly the wiki maintainer; the long-memory voice is a tonal mode of Jaromelu, not of this worker.

---

## Open questions

These will be revisited as the Archivist runtime is built.

1. **Skip-threshold tuning.** The current heuristic in principle 7 is a placeholder. Real threshold will emerge from watching revision noise on real sessions.
2. **Stub-promotion automation.** Whether `stub → draft` should ever auto-promote, or always require operator confirmation. Current design leans operator-confirmed; could relax once we trust the Archivist's section completeness.
3. **Cross-page transaction scope.** When a multi-page session partially fails, do we roll back all pages or commit the successful ones with a flag? Probably depends on which pages — relations are safer to commit partially than core entity pages.
4. **Continuity callback model.** Whether continuity links (Remark → prior Remarks) live in `wiki_relations` (with new `extends`/`contradicts_prior` types) or in a separate table. Leaning toward `wiki_relations` for unification.
5. **Long-memory voice mode disposition.** When and how to fold the prior `archivist.md` tonal-mode content into `jaromelu.md` and/or `dynamics.md`. Tracked as a follow-up; not blocking.

---

## Related

- [Wiki content pipeline](../../pages/wiki/content-pipeline.md) — runtime spec: managed agent, MCP toolset, session flow, page section conventions
- [Wiki overview](../../pages/wiki/overview.md) — schema, API, page types
- [Wiki page design](../../pages/wiki/page-design.md) — typography, components, callout vocabulary the Archivist writes against
- [Entity connections (draft)](../../architecture/drafts/wiki-entity-connections.draft.md) — `wiki_relations` table the Archivist curates
- [Crew Dynamics](dynamics.md) — where the Archivist sits in the internal reasoning flow
- [Jaromelu](jaromelu.md) — voice / tonal modes (where the prior Archivist tonal-mode content gets reabsorbed)
- [The Show (draft)](../../architecture/drafts/02-the-show.draft.md) — customer-facing framing of the crew
