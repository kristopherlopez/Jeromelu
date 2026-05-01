---
tags: [area/agents, subarea/system, status/live]
---

# Publishing

| | |
|---|---|
| **Worker** | `services/worker-publishing/app/main.py` |
| **Task Queue** | `publishing` |
| **Crew counterparts** | [Jaromelu](../crew/jaromelu.md) (voice), [Analyst](../crew/analyst.md) (consensus detection) |

This worker owns two workflows and a set of LLM activities. It's the bridge between structured claims and user-facing content — Jaromelu's voice lives here.

---

## FeedGenerationWorkflow

| | |
|---|---|
| **Workflow** | `services/worker-publishing/app/workflows/feed_generation.py` |
| **Purpose** | Synthesise extracted claims into opinionated feed events in Jaromelu's voice |

**Steps (sequential):**
1. `fetch_unprocessed_claims` — find claims not yet linked to any Event
2. `update_consensus_snapshots` — compute consensus scores, detect sentiment flips
3. `generate_review_data` — compare past predictions against actual match outcomes
4. `generate_feed_events` — LLM synthesis (OpenAI gpt-4o, temp 0.2) with character voice prompt
5. `persist_events` — write Event rows with SHA256 deduplication

**Returns:** `{generated, inserted, skipped}`

---

## KBGenerationWorkflow

| | |
|---|---|
| **Workflow** | `services/worker-publishing/app/workflows/kb_generation.py` |
| **Purpose** | Distill claims, stats, and events into curated knowledge base entries |

**Steps (parallel where possible):**
1. `generate_player_summaries` — third-person factual summaries (10 min timeout)
2. `generate_round_briefs` — matchup/bye/injury overviews (5 min)
3. `generate_decisions_log` — historical team selection log (5 min)
4. `generate_player_opinions` — first-person opinionated takes in Jaromelu voice (10 min)
5. `generate_source_digests` — one-paragraph per-source summaries (10 min)
6. `embed_kb_entries` — generate vector embeddings for RAG retrieval (5 min)

All LLM steps use `chat_json()` (OpenAI gpt-4o, temp 0.2, JSON mode).

**Retry policy:** 3 attempts, 5s initial interval, 2× backoff.

---

## LLM Activity Agents

Each LLM-powered activity inside `worker-publishing` calls OpenAI via `chat_json()` with a task-specific system prompt.

| Activity | File | LLM Task Type | Purpose |
|---|---|---|---|
| `generate_feed_events` | `activities/generate_events.py` | Characterisation | Convert structured claims into narrative feed events in Jaromelu's voice |
| `generate_player_summaries` | `activities/generate_kb.py` | Synthesis | Third-person factual player summaries from aggregated claims |
| `generate_player_opinions` | `activities/generate_kb.py` | Characterisation | First-person opinionated takes (bullish/bearish) in Jaromelu voice |
| `generate_round_briefs` | `activities/generate_kb.py` | Synthesis | Factual round overviews: matchups, byes, injuries, conditions |
| `generate_source_digests` | `activities/generate_kb.py` | Synthesis | One-paragraph summaries of what each source said |
| `generate_decisions_log` | `activities/generate_kb.py` | Synthesis | Historical record of Jaromelu's team selections |
| `embed_kb_entries` | `activities/generate_kb.py` | Embedding | Vector embeddings for RAG retrieval |
| `update_consensus_snapshots` | `activities/update_consensus.py` | None (deterministic) | Compute consensus scores, detect sentiment flips |
| `generate_review_data` | `activities/generate_reviews.py` | None (deterministic) | Match past predictions against actual player round scores |

LLM task types map to the categories in [`../../architecture/06-llm-architecture.md`](../../architecture/06-llm-architecture.md).

## Related

- Feed generation walkthrough: [`../../pages/feed/generation.md`](../../pages/feed/generation.md)
- Phase 2.2 tasks: [`../../todo/TODO.md`](../../todo/TODO.md#22-publishing-worker-servicesworker-publishing)
