---
tags: [area/operations, data-catalogue]
---

# knowledge_base

[← Data Catalogue](README.md) · [Lineage](../data-lineage/knowledge_base.md) · Layer 4 — Reasoning & output

Distilled, structured knowledge chunks embedded for RAG retrieval. Also stores Analysis articles.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| kb_id | UUID | PK | uuid4 | |
| kb_type | text | no | | `player_summary`, `round_brief`, `decision`, `opinion`, `source_digest`, `article_tips`, `article_totw`, `article_trades`, `article_captains`, `article_stocks`, `article_consensus` |
| person_id | UUID | yes | | FK → people |
| team_id | UUID | yes | | FK → teams |
| match_id | UUID | yes | | FK → matches |
| venue_id | UUID | yes | | FK → venues |
| round_id | UUID | yes | | FK → rounds |
| title | text | yes | | |
| content | text | no | | Markdown body |
| embedding | vector(1536) | yes | | For RAG retrieval |
| metadata_json | jsonb | no | {} | Player rankings, consensus counts, etc. |
| effective_round | int | yes | | |
| season | int | yes | | |
| source_claim_ids | UUID[] | no | [] | Attribution — claim UUIDs used |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | |
| expires_at | timestamptz | yes | | Optional TTL |

**Check:** at-most-one of typed FKs (`ck_knowledge_base_subject`) — subject is optional (round_brief / source_digest / article_* kinds have no subject)
**Indexes:** kb_type, (effective_round, season), person_id, embedding (HNSW / IVFFlat)
**FK:** person_id → people; team_id → teams; match_id → matches; venue_id → venues; round_id → rounds

Powers [Ask Me](../../pages/ask-me/overview.md) (RAG) and [The Analysis](../../pages/analysis/overview.md) (`article_*` types).
