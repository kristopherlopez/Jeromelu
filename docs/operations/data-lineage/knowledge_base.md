---
tags: [area/operations, data-lineage]
---

# Lineage: knowledge_base

[Schema: data-catalogue/knowledge_base.md](../data-catalogue/knowledge_base.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Distillation over [claims](claims.md) + [source_documents](source_documents.md) | — | **Primary** for `player_summary`, `round_brief`, `source_digest` kinds |
| Article generation pipelines | — | `article_*` kinds |

## Writers

- `scripts/insights/generate_round_tips.py` — round-tips article generator
- `scripts/insights/seed_mock_articles.py` — local-dev seed
- The Analysis pipeline (`docs/pages/analysis/overview.md`) — produces `article_tips`, `article_totw`, `article_trades`, `article_captains`, `article_stocks`, `article_consensus` kinds
- Ask-Me / RAG pipeline (`docs/pages/ask-me/overview.md`) — produces `player_summary`, `round_brief`, `source_digest` chunks for retrieval

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `kb_id` | derived | UUID, DB-side default |
| `kb_type` | writer | `player_summary`, `round_brief`, `decision`, `opinion`, `source_digest`, `article_tips`, `article_totw`, `article_trades`, `article_captains`, `article_stocks`, `article_consensus` |
| `person_id` / `team_id` / `match_id` / `venue_id` / `round_id` | writer | At-most-one (`ck_knowledge_base_subject`); article kinds have no subject |
| `title` | writer | Optional headline |
| `content` | writer | Markdown body |
| `embedding` | embedder | OpenAI ada-002 (1536d); HNSW/IVFFlat-indexed for RAG |
| `metadata_json` | writer | Player rankings, consensus counts, etc. |
| `effective_round`, `season` | writer | Time scope |
| `source_claim_ids` | writer | Attribution — array of `claim_id`s used |
| `created_at`, `updated_at` | derived | DB defaults |
| `expires_at` | writer | Optional TTL (e.g. weekly tips article expires when next round starts) |

## Notes

- Embedding column is the RAG retrieval surface. Rebuild via embedder script when `content` changes.
- `source_claim_ids` lets you trace any kb chunk back to the upstream claims that informed it.
