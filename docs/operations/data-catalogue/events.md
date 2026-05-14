---
tags: [area/operations, data-catalogue]
---

# events

[← Data Catalogue](README.md) · Layer 4 — Reasoning & output

Immutable audit trail of system activity. Entries are hashed for tamper detection.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| event_id | UUID | PK | uuid4 | |
| event_type | text | no | | |
| related_entity_ids | UUID[] | no | [] | |
| related_decision_id | UUID | yes | | FK → decisions |
| related_prediction_id | UUID | yes | | FK → predictions |
| related_claim_ids | UUID[] | no | [] | Claim ids this event references (no FK — array) |
| related_source_id | UUID | yes | | FK → sources |
| display_text | text | no | | |
| display_mode | text | no | | `watching`, `signal`, `thinking`, `prediction`, `action`, `review`, `sys`, `question`, `answer` |
| metadata_json | jsonb | no | {} | Free-form event payload |
| visibility | text | no | `public` | `public`, `private` |
| created_at | timestamptz | no | now() | |
| immutable_hash | text | yes | | SHA256 of event payload |

**Indexes:** event_type, created_at, visibility
**FK:** related_decision_id → decisions; related_prediction_id → predictions; related_source_id → sources
