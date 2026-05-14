---
tags: [area/operations, data-catalogue]
---

# claims

[← Data Catalogue](README.md) · [Lineage](../data-lineage/claims.md) · Layer 3 — Content & claims

The single extraction table — every assertion or annotation pulled from a transcript span. Mig 036 absorbed the old `source_annotations` table by expanding `claim_type` to include annotation-flavoured kinds. Subjects are not stored on the claim row itself; they're rows in [claim_associations](claim_associations.md) with `role='subject'`.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| claim_id | UUID | PK | uuid4 | |
| document_id | UUID | yes | | FK → source_documents |
| quote_id | UUID | yes | | FK → quotes |
| claim_type | text | no | | Fantasy-actionable: `buy`, `sell`, `hold`, `captain`, `avoid`, `breakout`, `matchup_edge`. Annotation-flavoured (mig 036): `mention`, `theme`, `subtopic`, `sentiment`, `tactical_tag`, `highlight`. |
| claim_text | text | yes | | Human-readable summary |
| polarity | float | yes | | Positive/negative sentiment |
| strength | float | yes | | Conviction level |
| effective_round | int | yes | | NRL round this applies to |
| season | int | yes | | NRL season year |
| start_ts | float | yes | | Video timestamp start (seconds) |
| end_ts | float | yes | | Video timestamp end (seconds) |
| payload_json | jsonb | no | {} | Kind-specific payload (sentiment scores, sub-topic metadata, etc.) |
| extracted_at | timestamptz | no | now() | |

**Indexes:** claim_type, document_id, (effective_round, season)
**FK:** document_id → source_documents; quote_id → quotes

Subjects: query `claim_associations WHERE claim_id = X AND role = 'subject'` to dispatch on which typed FK is set (person/team/match/venue/round). The fantasy-claim use case filters by `claim_type IN ('buy','sell','hold','captain','avoid','breakout','matchup_edge')`.
