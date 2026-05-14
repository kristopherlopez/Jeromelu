---
tags: [area/operations, data-lineage]
---

# Lineage: claims

[Schema: data-catalogue/claims.md](../data-catalogue/claims.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| `process-transcript` / `analyse-transcript` skills | — | **Primary** — multi-pass claim extraction from cleaned transcripts |
| `verify-claims` skill | — | Updates `claim_text`, `strength`, `polarity` after verification pass |
| SC notes extractor | [data-sources/supercoach/classic-players-cf.md](../data-sources/supercoach/classic-players-cf.md) | One claim per SC note (846 rows shipped) |

## Writers

- `process-transcript` skill — multi-pass extraction; writes pending claims with `claim_type` + `payload_json`
- `verify-claims` skill — Haiku agent per claim re-checks `claim_type`, `claim_text`, `strength`, `polarity`, `start_ts`, `end_ts` against the clean transcript
- `upload-transcript` skill — persists verified claims to DB
- `services/api/app/scout/supercoach_roster/notes_extractor.py` — SC notes path

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `claim_id` | derived | UUID, DB-side default |
| `document_id` | extractor | FK → source_documents |
| `quote_id` | extractor | FK → quotes (the quote backing this claim) |
| `claim_type` | extractor | **Fantasy-actionable** (`buy`, `sell`, `hold`, `captain`, `avoid`, `breakout`, `matchup_edge`) or **annotation-flavoured** (`mention`, `theme`, `subtopic`, `sentiment`, `tactical_tag`, `highlight`) — mig 036 absorbed `source_annotations` |
| `claim_text` | extractor | Human-readable summary |
| `polarity` | extractor / verifier | -1.0 to +1.0 |
| `strength` | extractor / verifier | Conviction 0-1 |
| `effective_round` | extractor | NRL round this applies to |
| `season` | extractor | NRL season year |
| `start_ts`, `end_ts` | extractor | Video timestamp range |
| `payload_json` | extractor | Kind-specific (sentiment scores, sub-topic metadata, tactical tags, etc.) |
| `extracted_at` | derived | DB default `now()` |

## Subjects

Subjects (the player/team/match/venue/round a claim is *about*) live in [claim_associations](claim_associations.md), not on the claim row. Query `claim_associations WHERE claim_id = X AND role = 'subject'` and dispatch on which typed FK is set.

## Notes

- Tracks all opinions/predictions/themes pulled from external content per [[project_ledger_direction]].
- The `verify-claims` skill spins up a Haiku agent per claim (cheap, parallel) to cross-check the extraction against the source. Writes confidence/correction back.
