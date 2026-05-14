---
tags: [area/operations, data-catalogue]
---

# scout_presenter_candidates

[← Data Catalogue](README.md) · [Lineage](../data-lineage/scout_presenter_candidates.md) · Layer 3 — Content & claims

Presenter Scout's staging inbox. Distinct from [scout_candidates](scout_candidates.md) (which discovers *channels* and *videos*) — this one discovers *people who present* a known channel. The Presenter Scout agent files findings here; humans confirm/reject in the admin "Presenters" tab. Confirmation creates (or links to) a [people](people.md) row and writes a [source_presenters](source_presenters.md) association. See migration 052 and [docs/agents/system/presenter-scout.md](../../agents/system/presenter-scout.md).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| channel_id | UUID | no | | FK → channels (CASCADE) |
| name | text | no | | "Denan Kemp" |
| role | text | no | | `host`, `co-host`, `regular`, `frequent-guest` |
| evidence_json | jsonb | no | [] | Array of `{url, snippet}`. Snippet must mention the name (auto-validated at insert). |
| llm_confidence | float | yes | | Agent's own 0.0–1.0 score |
| notes | text | yes | | Free-form agent commentary; reviewer notes appended on reject |
| existing_person_id | UUID | yes | | FK → people. Best-effort dupe hint when `lookup_existing_people` returned a match |
| status | text | no | `pending` | `pending`, `confirmed`, `rejected` |
| reviewed_at | timestamptz | yes | | |
| reviewed_by | text | yes | | |
| confirmed_person_id | UUID | yes | | FK → people. Set on confirm — the Person this candidate became |
| run_id | text | yes | | Groups all candidates from one Presenter Scout run |
| discovered_at | timestamptz | no | now() | |

**Indexes:** (channel_id, status); partial unique on (channel_id, lower(name)) WHERE status='pending' — re-runs don't double-file pending names but a previously-rejected name CAN re-surface.
**FK:** channel_id → channels (CASCADE); existing_person_id, confirmed_person_id → people (SET NULL).
