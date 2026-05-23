---
tags: [area/architecture, subarea/agents, subarea/wiki]
status: draft
---

# Archivist Build (Draft)

> Draft. Last reviewed: 2026-05-12.
>
> First-pass implementation plan for the Archivist crew worker — the wiki-maintaining Claude Managed Agent. Engages with the open implementation questions in [`content-pipeline.md`](../../pages/wiki/content-pipeline.md) and the relations dependency in [`wiki-entity-connections.draft.md`](wiki-entity-connections.draft.md). Role is canonicalised in [`docs/agents/crew/archivist/README.md`](../../agents/crew/archivist/README.md); this doc does not re-litigate it.

---

## What this draft is for

The role spec is settled. What's not settled is *how to build the runtime*: session granularity, MCP transport, where it runs on prod, what the smallest useful slice looks like, how to test prose generation, and how relations work folds in (or doesn't) on day one. This draft proposes answers and a phased rollout.

---

## Decisions to lock before any code is written

Each decision states the options briefly, the recommendation, and the reasoning. These map onto open questions in `content-pipeline.md` plus three new ones surfaced by the implementation perspective.

### D1. Session granularity (Open Q1)

**Options:** one session per page · one session per related batch · one session per trigger event.

**Recommendation: one session per *trigger event*, scoped to the natural blast radius of that trigger.** A claims-upload trigger names the player(s) and advisor(s) the new claims touch and runs a single session that updates all of them; a post-round-stats trigger runs a session per match (~26 player pages + 2 team pages + 1 round page). Per-page sessions would cripple cross-page integrity (principle 3); a "big batch per trigger" maximises cross-referencing and keeps the cost story sane (one prompt-cache warmup amortised over N pages). Blast radius is bounded by the trigger's natural scope, not by collecting everything in flight.

### D2. Automation level (Open Q2)

**Recommendation: operator-triggered for the first rollout (Phases 1-2); auto-trigger from Phase 3 onward, behind a feature flag per trigger type.** We don't yet have the revision-history signal to tune the skip threshold (principle 7) — running automatic before that produces noise we can't grade. Operator-triggered also gives a natural budget cap (one button click = one bounded run). Once we trust the noise level, claims-upload auto-trigger is the safest first switch (it already runs after a manual `/upload-transcript` — the operator presence is implicit).

### D3. KB role (Open Q3)

**Recommendation: bypass KB on day one; the Archivist reads claims/stats directly.** KB adds a synthesis layer that is itself an LLM artifact — feeding LLM-synthesised text into another LLM-synthesised wiki dilutes provenance (principle 2) and makes "where did this sentence come from?" harder to answer. The Archivist's MCP `get_kb_entries` operation stays in the spec for later use, but is not wired in Phase 1. Re-evaluate once we observe whether Archivist sessions struggle with raw-claims volume on dense players (Cleary, Trbojevic).

### D4. Conflict handling (Open Q4)

**Recommendation: report contradictions structurally; do not adjudicate.** The page renders both claims via the existing `Trust List` / `Verdict` callout vocabulary in [page-design.md](../../pages/wiki/page-design.md). The Archivist's job is to surface that SC Playbook says X and NRL Physio says Y; weighting and the call belong to Jaromelu's voice in a Remark. This is a direct application of principle 8 (encyclopedic voice). Implementation: when the Archivist detects two claims with opposite `polarity` on the same subject within a relevance window, it writes both into `## Expert Opinions` under a `:::trust-list` callout. No advisor-accuracy weighting in V1 — that's a Phase 4 concern that depends on Bookkeeper outputs which are themselves not built.

### D5. MCP server location (Open Q6)

**Recommendation: embed as FastMCP routes alongside the FastAPI app.** Reasons: (a) the MCP server is just a SQL gateway with the same connection pool, model imports, and auth model the API already has; (b) the Lightsail prod box runs api/web/postgres/caddy and nothing else — a separate MCP service means a new container, new health check, new restart story for marginal isolation gain; (c) the API process already imports `jeromelu_shared.db.models`, which is exactly what the MCP tools need. Mount under `services/api/app/mcp/wiki_mcp.py` as a sibling router. The MCP transport in 2026 supports HTTP+SSE — the agent calls localhost:8000/mcp/wiki when it runs in-process or via the same docker network. Heavy ML stays out of this path; the API container stays lean.

### D6 (new). Where does the Archivist *process* run?

**Options:** in the API process · sibling Python process on the same box · separate worker service.

**Recommendation: same process as the API, invoked by a FastAPI background task or admin endpoint.** Sessions are minutes-long, not hours. The API already has an event loop, the SQLAlchemy session factory, and the Anthropic client. A separate worker buys nothing on the prod footprint we have today (no Temporal, no Celery, no Redis). When sessions become too long-running to block API throughput we revisit — at that point the upgrade is ASGI background tasks → a small dedicated `services/archivist-worker` container, but that's a Phase 5 problem.

### D7 (new). Relations work — bake in or defer?

**Recommendation: design the extension point in Phase 1, build relations support in Phase 3.** The relations draft (`wiki-entity-connections.draft.md`) is unapproved and proposes its own phased rollout (schema → API → derived → graph → curation). Forcing the Archivist to depend on `wiki_relations` migrations that haven't landed couples two unfinished things. Concrete: the MCP tool palette and system prompt are designed with placeholder slots for `upsert_wiki_relation` / `close_wiki_relation`; the loop dispatches on tool name with a clean fallback when the table doesn't exist. When the relations schema lands (its Phase 0), the Archivist gets the operations switched on without touching its core architecture. **What this means for prose:** in Phase 1-2, the Archivist writes `[[slug]]` links in prose but does not curate `wiki_relations` rows. The Connections sidebar simply isn't rendered yet (Connections render is owned by relations work, not by us).

### D8 (new). Schema reality check — entity model has shifted

The role spec (and almost every doc this draft links to) keeps using `entities` / `entity_id` terminology. **The schema dropped the polymorphic `entities` table in migration 038 (`038_drop_entities_and_polymorphic_fks.sql`).** That migration also dropped `entity_roles`, `player_attributes`, and every `*_entity_id` FK column on output tables. `wiki_pages` now has typed FKs (`person_id`, `team_id`, `match_id`, `venue_id`, `round_id`, `channel_id`) under the rebuilt `ck_wiki_page_subject` exactly-one CHECK. Identity tables are now `people`, `player_attributes`, `people_roles`, plus typed `teams`, `venues`, `matches`, `rounds`. Claim/prediction/decision subject linkage moved into `claim_associations` / `prediction_associations` / `decision_associations`.

**This is a correctness blocker for the Archivist build, but it is also a wider docs-vs-schema drift that affects almost every doc this plan references.** The Archivist's MCP read/write surface and system prompt must speak typed FKs and use the association tables, not `entity_id` and not `entities`. **Recommended sequencing: a docs reconciliation pass (entities → people + typed FKs across `archivist.md`, `content-pipeline.md`, `wiki-entity-connections.draft.md`, `entity-roles.md`, `04-information-architecture.md`) lands *before* Phase 0 of this build.** Otherwise the implementation team works against ghost schemas.

---

## Recommended starting scope

The thin-team-claims problem is real: most extracted claims are player-focused, channels and rounds get little prose-worthy material today. **Recommendation: start with player pages, Wests Tigers as the dogfood squad.**

Why:
- Player pages have the densest upstream signal (claims + player_rounds + teamlists + injuries).
- Wests Tigers gives us ~30 seeded player pages — large enough to see cross-page integrity behaviour, small enough to eyeball every revision by hand.
- A first rewrite of the Tigers' player pages produces a usable artifact even if the team page itself stays a stub.

Sequence:
1. Phase 1 dogfood: pick 4 Tigers players with rich claim coverage and recent roster movement, run a session that updates all four from current claims.
2. Phase 2 widens to the full Tigers squad (~30 pages) under one trigger.
3. Phase 3 adds team and round pages once the player layer is solid.

Channel pages — Phase 4. Advisor pages — deferred until speaker diarisation has produced enough quotes per advisor to write `## Recent Calls` from.

---

## Phasing

### Phase 0 — Docs reconciliation + audit prep (one PR each, ~1 day total)

**Phase 0a — docs reconciliation (per D8).** Sweep `archivist.md`, `content-pipeline.md`, `entity-roles.md`, `wiki-entity-connections.draft.md`, `04-information-architecture.md`, and any other doc referencing `entities` / `entity_id` / `entity_roles` / `player_attributes`. Replace with typed FKs and the association tables. This is precondition for everything below.

**Phase 0b — agent_id constraint extension.** Migration: extend `ck_agent_runs_agent_id` to include `'archivist'`. Update `__table_args__` in `models.py` to match. (Pattern from prior agent additions; must precede any first run or `record_agent_started` will INSERT-fail.)

No new tables in Phase 0. Wiki tables already exist; relations table is deferred.

### Phase 1 — End-to-end smoke (the proof slice)

The smallest thing that proves the architecture: one player page rewrite, hand-triggered, with full audit.

- **MCP server (`services/api/app/mcp/wiki_mcp.py`)** — minimal toolset: `get_wiki_page`, `update_wiki_page`, `get_claims`, `get_player_stats`, `search_wiki_pages`. FastMCP-mounted route on the existing API. Auth: the agent runs in-process, MCP is bound to localhost, no auth in V1. Tools speak typed FKs (`person_id`/`team_id`/etc) and read claim subjects via `claim_associations`.
- **Archivist loop (`services/api/app/archivist/loop.py`)** — close clone of `scout/loop.py` skeleton: `AgentAuditLog`, `AgentBounds`, `record_agent_started/ended`, manual streaming loop, dispatch on client-side tool calls. Default model `claude-sonnet-4-6`. Default bounds tighter than Scout's because sessions are smaller: `max_turns=15, max_tool_calls=40, max_wall_seconds=600, max_budget_usd=0.50` per page.
- **System prompt (`services/api/app/archivist/prompt.py`)** — skip-threshold heuristic from principle 7, the section vocabulary for player pages, encyclopedic voice rules, `[[slug]]` link convention, the explicit rule that `update_wiki_page` is the only mutation path and must include a revision summary.
- **Custom tools (`services/api/app/archivist/tools.py`)** — `update_wiki_page` (calls MCP), section diffing helpers if the agent needs them, `create_stub` (for principle 4 — when prose links to a missing page).
- **CLI (`services/api/app/archivist/cli.py`)** — `python -m app.archivist.cli --slug jarome-luai --trigger manual`. Mirrors the Scout CLI structure exactly.
- **Test fixtures** — a sample brief plus the four-Tigers payload, runnable as a smoke test against a local DB seeded from `seed_wiki.py`.

**Phase 1 done = one operator runs `--slug jarome-luai`, sees the prose update, sees the row in `wiki_revisions`, sees the run summary in `agent_runs`, and the diff is something the operator would publish.**

### Phase 2 — Multi-page session + skip threshold tuning

- Trigger format expands from one slug to a list of slugs with a shared brief ("New claims from SC Playbook Round 8: tom-trbojevic, nathan-cleary, …").
- Skip-threshold logic moves into the system prompt and gets exercised — most pages in a batch should produce no revision because the new claim doesn't move the picture.
- `wiki_revisions.source_trigger` taxonomy from `content-pipeline.md` enforced (`archivist/claims-upload`, `archivist/manual`, etc.).
- First operator dashboard view: a "recent Archivist sessions" page showing run_id, pages touched, pages skipped, total cost. No new endpoint — uses the existing `agent_runs` query.

### Phase 3 — Relations integration + auto-trigger first switch

- Depends on relations work landing (`wiki_relations` table + `upsert_wiki_relation` MCP tool exposed).
- Archivist system prompt extended with the curated relation vocab; tools wired through; `source='archivist'` stamped on every relation row.
- Auto-trigger from `/upload-transcript` claims-upload via FastAPI background task. Behind `ARCHIVIST_AUTO_TRIGGER_CLAIMS=true` env flag for kill-switch control.

### Phase 4 — Team and round page coverage; channel-page Recent Sources

- Team-page scaffold from `content-pipeline.md` §"Team Pages" wired up.
- Round pages auto-trigger after team-list ingestion lands.
- Channel pages: Archivist updates `## Recent Sources` when new sources are ingested.

### Phase 5 — Continuity callbacks (Remarks → wiki)

- Depends on Jaromelu publishing Remarks (separate work).
- Bucket 4 of the role spec: Archivist links new Remarks back to prior Remarks on the same subject.
- Probably needs the worker to leave the API process at this point (frequency goes up, latency tolerance goes down).

---

## Architectural risks

The things that hurt if we get them wrong and discover late.

1. **Prompt-cache thrash across pages.** Each page rewrite needs the page's current content in the prompt — that's per-page input that doesn't cache. If we don't structure the multi-page session as "static system prompt cached + per-page user message", we burn the cache hit rate and per-page cost balloons. Mitigation: explicit cache_control on the system block (Scout's pattern) and per-page user messages within one session, not separate sessions.

2. **The MCP write surface is dangerous.** `update_wiki_page` mutates published prose. A bad agent loop could overwrite the entire content with a partial section. Mitigation: the MCP `update_wiki_page` operation must take `section_heading` + `section_content` and merge into existing markdown server-side, not accept a full content blob. The agent never sends complete page content. Bound: a single `update_wiki_page` call updates exactly one section.

3. **Stub explosion (principle 5 hazard).** "Wiki-link liberally → orphans become stubs" can generate dozens of stubs per session if the agent over-links. Mitigation: rate-limit stub creation per session (e.g. ≤5 stubs/session, hard cap in the MCP tool).

4. **Schema drift (D8 above).** The role spec and content-pipeline use `entities` / `entity_id`. The schema uses typed FKs and association tables. If the system prompt and MCP tool input schemas don't match the typed reality, every agent call will fail with a FK error. Phase 0a is the docs-side cleanup; an MCP integration test that round-trips a real query before any LLM call is the code-side guard.

5. **Relations without relations.** If we ship Phase 1 and the relations work never lands, the Connections sidebar stays empty forever and we never validate principle 6. Tracking risk, not blocker — Phase 1 is still useful as a prose-only wiki maintainer.

6. **Cross-page transactionality.** If page 4 of 6 fails mid-session, what happens to pages 1-3? V1 punt: each `update_wiki_page` commits independently, and a session-end summary reports failures for operator follow-up. This violates principle 3 in the failure case, but full-session transactionality is too expensive for V1 and we accept the risk while operator-triggered (D2). Revisit when we auto-trigger.

7. **Editorial drift over time.** The agent's voice will drift from "encyclopedic" (principle 8) toward something punchier or chattier as the prompt accumulates patches. Mitigation: a small DeepEval suite under `tests/evals/archivist/` with 10-20 fixed prompts that grade voice neutrality, factual grounding, and `[[slug]]` link integrity. Costs $$ per run; gate on PRs that touch the system prompt.

---

## Cost, testing, rollout

### Cost model

Per-page Sonnet 4.6 cost estimate, assuming ~3k input tokens per page (current content + 5-10 new claims + section scaffold) and ~1.5k output tokens per modified section:

- Cached system prompt: ~$0 marginal after the first warmup
- Per-page input (~3k uncached): ~$0.009
- Per-page output (~1.5k): ~$0.022
- Per-page net: ~$0.03 with cache hit, ~$0.05 cold

A 30-page Tigers session: ~$1.00. Default `max_budget_usd=0.50` per *page-equivalent* — for a 30-page session the bound becomes session-level and lifts to ~$2.00. Document this — Scout's `max_budget_usd` is per-run, the Archivist's effectively scales with session size and the bound logic needs to reflect that.

### Testing

Three tiers, mirroring the project's existing `tests/` layout:

- **Unit (`tests/unit/api/archivist/`)** — section diffing, slug derivation, MCP tool schemas, prompt assembly. No LLM, no DB. Should cover most regressions.
- **Integration (`tests/integration/archivist/`)** — round-trip: seeded DB → MCP server → tool calls → wiki_page rows. No LLM (mocked Anthropic client returning fixed tool-use blocks). Validates the loop scaffolding without burning $$.
- **Evals (`tests/evals/archivist/`)** — DeepEval LLM-graded suites. ~15 fixtures: each is a player-page state + a brief, scored on voice neutrality, factual grounding to provided claims, no hallucinated stats, `[[slug]]` correctness, skip-threshold respected (negative cases where prose should not change).

Dogfood loop: operator runs `--slug ...` against staging weekly, reads every diff, writes a one-paragraph note on what the Archivist did well or badly. After 10 weeks, the eval suite should be calibrated to those notes.

### Rollout

1. Phase 1 ships disabled by default — no auto-trigger, no public surface, runs against staging.
2. Operator dogfoods Tigers player pages for 2 weeks. Iterates on system prompt.
3. Phase 2 ships, still operator-triggered, opened to all player pages.
4. After ~4 weeks of clean revision history, Phase 3 enables claims-upload auto-trigger (one trigger type at a time).
5. Each subsequent auto-trigger type goes through the same 2-week observation window.

---

## Documentation Updates

Per CLAUDE.md doc discipline. Treat this list as the changeset checklist for the implementation PRs.

| Doc | Change |
|-----|--------|
| `docs/agents/crew/archivist.md` | (Phase 0a) Replace `entities` / `entity_id` references with typed FKs (`person_id`, `team_id`, etc) and `claim_associations`. (After Phase 1) Add §"Implementation status" pointing to this draft. |
| `docs/pages/wiki/content-pipeline.md` | (Phase 0a) Same FK sweep as above; correct MCP operations table (`get_entity` → typed `get_person`/`get_team`/etc, or one polymorphic `get_subject(kind, id)`). (Per build) Resolve Open Questions 1, 2, 3, 6 with the decisions above; add §"MCP transport — FastMCP on the API". |
| `docs/concepts/entity-roles.md` | (Phase 0a) Either rewrite around `people_roles` and `player_attributes`, or move the doc to `docs/concepts/people-roles.md` and rename concepts throughout. |
| `docs/architecture/04-information-architecture.md` | (Phase 0a) Update data-model diagram + tables to reflect typed identity. |
| `docs/architecture/drafts/wiki-entity-connections.draft.md` | (Phase 0a) `wiki_relations` schema needs typed-FK pair instead of `(a_entity_id, b_entity_id)` — likely `(a_kind, a_id, b_kind, b_id)` or per-kind tables. Material redesign, not just a rename. |
| `docs/agents/system/agent-audit.md` | Add `archivist` to the example agent_id list; add a note on session-scaled budget bounds (Archivist's wrinkle). |
| `docs/agents/system/README.md` | Add Archivist to the crew list with link. |
| New: `docs/agents/system/archivist-runtime.md` | Companion to `archivist.md` (which is role spec), this is the operational doc — CLI usage, environment, debugging a run, reading the audit trail. Pattern lifted from Scout's docs. |
| `packages/db/migrations/0NN_extend_agent_runs_archivist.sql` | The CHECK-constraint extension. |
| `services/api/app/archivist/README.md` | Module-level README describing layout (`loop.py`, `prompt.py`, `tools.py`, `cli.py`) — mirrors Scout's directory comment style. |
| `CLAUDE.md` | Add a one-liner that the Archivist owns wiki prose mutation — no other code path writes to `wiki_pages.content`. |
| Once relations land: `wiki-entity-connections.draft.md` | Move from draft to merged; cross-link from this draft. |

---

## Open questions surfaced by this draft

These are *new* questions the implementation perspective surfaces beyond what's in `archivist.md` and `content-pipeline.md`. Stating them here so the next reviewer can tick or push back.

1. **Per-section vs per-page MCP write granularity.** Risk #2 above pushes for per-section. Does that interact badly with the agent's freedom to restructure a page? Lean toward per-section in V1, accept that bigger restructures need an operator-only `replace_full_page` escape hatch.
2. **Section preservation when the schema changes.** If we rename `## Expert Opinions` to `## Reactions` next quarter, every page's existing prose breaks. Owned by whoever changes section vocab, not by the Archivist — but worth a written contract that section vocab changes ship with a content-migration script.
3. **Cost attribution per trigger type.** Useful for Phase 3 auto-trigger decisions: which trigger types are cheap (small blast radius) vs expensive (round-end stats touch every page). Add a `trigger_type` column to `agent_runs.detail_json` from day one so the data is there when we need it.
4. **What happens when the LLM disagrees with the skip-threshold instruction.** Principle 7 says don't rewrite. The agent will sometimes rewrite anyway if the prose feels stale. We discover this only through the eval suite; budget for one prompt-engineering iteration per phase to retune.
5. **Test data lifecycle.** Eval fixtures need to be stable — but they reference live entity slugs. Fixture-vs-live drift is real. Snapshot the entity rows used in evals into a JSONL fixture and load from there, not from the live DB.
6. **`wiki_relations` shape under typed identity.** Per D8 fallout: the relations draft assumes a `(a_entity_id, b_entity_id)` shape that is no longer expressible against the schema. Two options worth thinking about before relations lands: (a) `(a_kind, a_id, b_kind, b_id)` polymorphic shape, indexed per kind; (b) per-kind relation tables (`person_team_relations`, `person_person_relations`, etc.). (a) keeps it one table at the cost of FK looseness; (b) keeps FKs tight at the cost of N tables.

---

## Drafting notes (delete before merge)

Written from the implementation perspective on top of two settled spec docs. The biggest divergence from those specs is calling out the typed-FK schema reality (D8) — the role spec's "entity_id" framing predates migration 038 and needs a sweep across many docs, not just the Archivist ones. That's Phase 0a; it's a precondition, not Archivist work.

The phasing leans deliberately conservative on auto-triggering. The cheap mistake is shipping fast and writing a thousand bad revisions across the wiki before we notice the system prompt drifts; the expensive mistake is shipping slow and never validating the cross-page integrity story. Phase 1's dogfood-the-Tigers slice is small enough to read every diff by hand, which is the right calibration for the first 4 weeks.

The relations decision (D7) is the one I'm least confident about. If the relations draft gets approved and merged in the same window as Archivist Phase 1, baking it in is cheaper than retrofitting. If it slips a quarter, the deferral is right. Worth a check before locking — and worth folding the D8 typed-FK fallout (Open Question 6 above) into the relations draft revision when we get there.
