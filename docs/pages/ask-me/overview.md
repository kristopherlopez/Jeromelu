---
tags: [area/pages, subarea/ask-me]
---

# Ask Me

Status: **Live**

Route: `/ask` (also integrated into `/` feed as Twitch-style chat)
Code: `services/api/app/routers/feed.py` (chat endpoint), `services/web/src/app/ask/`, `services/web/src/app/feed/`

---

## Summary

Ask Me lets users chat with Jaromelu about NRL SuperCoach strategy. It uses a curated knowledge base (RAG) rather than raw transcript chunks. Analysis articles (see [The Analysis](../analysis/overview.md)) feed into the same KB, so Ask Me automatically surfaces them.

## Architecture

```
User question
    |
    v
Embed query (text-embedding-3-small)
    |
    v
Vector search knowledge_base (pgvector cosine similarity)
    |
    v
Build context from top-K KB entries
    |
    v
LLM call (gpt-4o) with Jaromelu system prompt + context
    |
    v
Return answer + source attribution
```

## Knowledge Base

The `knowledge_base` table stores distilled, structured knowledge maintained by the `KBGenerationWorkflow` Temporal workflow.

### KB Entry Types

| Type | Description | Source |
|------|-------------|--------|
| `player_summary` | Consolidated player profile: form, price, breakeven, consensus | Claims + PlayerRound stats |
| `round_brief` | Round overview: matchups, byes, conditions | Round-scoped claims |
| `decision` | Jaromelu's past trades/captain picks + outcomes | Events (action/prediction type) |
| `opinion` | Jaromelu's opinionated stance on a player | Aggregated claim sentiment |
| `source_digest` | Per-source summary of key calls | Claims grouped by source |

### KB Worker

`KBGenerationWorkflow` runs on the publishing task queue after feed generation. Activities:

1. `generate_player_summaries()` — one per active player
2. `generate_round_briefs()` — one per upcoming round
3. `generate_decisions_log()` — from action/prediction events
4. `generate_player_opinions()` — for players with 3+ claims
5. `generate_source_digests()` — per processed source
6. `embed_kb_entries()` — batch embed all new/updated entries

## Temperature Modes

The system prompt has three personality variants:

| Mode | LLM Temp | Behaviour |
|------|----------|-----------|
| Straight | 0.3 | Helpful, direct, clear recommendations |
| Sharp | 0.6 | Confident, cutting, strong opinions |
| Roast | 0.8 | Savage, mocks bad decisions, still accurate |

## API

The Ask Me feature is now integrated into the feed as a Twitch-style chat. Questions and answers are persisted as feed events.

**Primary endpoint** (creates feed events):
```
POST /api/feed/ask
Body: { question: string, temperature: "straight"|"sharp"|"roast" }
Response: { question_item: FeedItem, answer_item: FeedItem }
```

**Legacy endpoint** (deprecated — no events created):
```
POST /api/ask
Body: { question: string, temperature: "straight"|"sharp"|"roast" }
Response: { answer, sources[], players[], kb_entries_used[] }
```

## Evaluation

DeepEval test suite at `tests/evals/` with golden examples at `tests/evals/golden/ask_me_golden.yaml`.

Metrics: Faithfulness, Hallucination, Answer Relevancy, NRL Voice (GEval), No Fabrication (GEval).

## Key Files

- **KB model**: `packages/shared/jeromelu_shared/db/models.py` (KnowledgeBase class)
- **KB worker**: `services/worker-publishing/app/activities/generate_kb.py`
- **KB workflow**: `services/worker-publishing/app/workflows/kb_generation.py`
- **RAG module**: `packages/shared/jeromelu_shared/rag.py`
- **API router**: `services/api/app/routers/feed.py` (POST /api/feed/ask)
- **Legacy API**: `services/api/app/routers/ask.py` (deprecated)
- **Frontend**: `services/web/src/app/feed/` (merged into feed)
- **Evals**: `tests/evals/`
