# The Analysis

Status: **Live**

Route: `/insights` (nav label: **The Analysis**)
Code: `services/web/src/app/insights/`

---

## Summary

The Analysis is Jaromelu's editorial content hub. Each round, Jaromelu generates opinionated analytical articles covering SuperCoach strategy — trade targets, captain picks, team of the week, and podcast consensus.

Articles are generated via LLM using the existing claims pipeline (podcast extraction) and PlayerRound stats as structured data inputs. They're stored as KnowledgeBase entries, which means they automatically feed back into the RAG pipeline for [Ask Me](../ask-me/overview.md).

> The route is historically `/insights`; the user-facing label is **The Analysis**. Internal code, tables, and kb_type prefixes still use `insights` / `article_*`.

## Content Types

| Type | kb_type | Description |
|------|---------|-------------|
| SuperCoach Tips | `article_tips` | Round preview covering captain picks, trade targets, players to avoid |
| Team of the Week | `article_totw` | Best performers from the previous round, one per SC position |
| Trade Targets | `article_trades` | Players to buy/sell based on price trends and podcast consensus |
| Captain Picks | `article_captains` | Ranked captain recommendations with conviction levels |
| Stocks Up / Down | `article_stocks` | Rising and falling players based on form, price, and sentiment |
| Podcast Consensus | `article_consensus` | Cross-source comparison of what each podcast is saying |

## Architecture

### Storage

Articles use the existing `knowledge_base` table with `kb_type` values prefixed with `article_`. No new tables required.

Key fields used:
- `title` — article headline
- `content` — full markdown body (LLM-generated)
- `embedding` — vector embedding for RAG retrieval
- `effective_round` / `season` — which round the article covers
- `metadata_json` — structured data (player rankings, consensus counts) for frontend visualisations
- `source_claim_ids` — array of claim IDs used to generate the article (attribution)

### Generation Pipeline

1. **Data query**: Pull claims + PlayerRound stats for the target round
2. **Context building**: Aggregate consensus, merge with player stats
3. **LLM generation**: Call `chat_text()` with Jaromelu's voice prompt + article-specific instructions
4. **Storage**: Save as KB entry with embedding (idempotent per kb_type + round + season)

Generator scripts live in `scripts/insights/`:
- `generate_round_tips.py` — SuperCoach Tips
- (Phase 2) `generate_totw.py`, `generate_trades.py`, `generate_captains.py`, `generate_stocks.py`, `generate_consensus.py`
- (Phase 2) `generate_all.py` — unified runner

Shared utilities in `packages/shared/jeromelu_shared/insights.py`.

### API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/insights` | GET | List articles (filterable by type, round, season; cursor pagination) |
| `/api/insights/{kb_id}` | GET | Single article with full content and source attribution |

### Frontend

- `/insights` — article list with type filter badges, grouped by round
- `/insights/{kb_id}` — full article reader with markdown rendering and source attribution
- Nav label: **The Analysis** (in the orbital nav bubbles)

## History

This page replaced the former Squad page (`/squad`), which tracked Jaromelu's personal SuperCoach team roster. The squad DB tables (`squad_slots`, `squad_trades`) remain in the schema but are no longer actively used.

## RAG Integration

Because articles are stored as KB entries with embeddings, [Ask Me](../ask-me/overview.md) automatically retrieves them when answering related questions. For example, asking "who should I captain this week?" will surface the latest `article_captains` entry alongside `player_summary` entries.
