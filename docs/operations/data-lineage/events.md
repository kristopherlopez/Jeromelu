---
tags: [area/operations, data-lineage]
---

# Lineage: events

[Schema: data-catalogue/events.md](../data-catalogue/events.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| All system activity (audit trail) | — | **Primary** — append-only |

## Writers

Any system component that produces user-visible activity:
- Scout pipelines emit `display_mode='watching'` / `'thinking'` events as they discover content
- Reasoning agents emit `display_mode='signal'` / `'prediction'` / `'action'` events
- Wiki edits emit `display_mode='review'` events
- System lifecycle emits `display_mode='sys'` events
- Q&A surface emits `display_mode='question'` / `'answer'` events

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `event_id` | derived | UUID, DB-side default |
| `event_type` | writer | Free-text category (e.g. `scout.discovered`, `analyst.diarised`) |
| `related_entity_ids` | writer | UUID array (legacy polymorphic — pre-mig-038) |
| `related_decision_id` | writer | FK → decisions |
| `related_prediction_id` | writer | FK → predictions |
| `related_claim_ids` | writer | UUID array (no FK constraint — claims may be ephemeral pre-upload) |
| `related_source_id` | writer | FK → sources |
| `display_text` | writer | Human-readable line |
| `display_mode` | writer | `watching`, `signal`, `thinking`, `prediction`, `action`, `review`, `sys`, `question`, `answer` |
| `metadata_json` | writer | Free-form payload |
| `visibility` | writer | `public` (shown in UI feed) or `private` |
| `created_at` | derived | DB default `now()` |
| `immutable_hash` | writer | SHA256 of event payload (tamper detection) |

## Notes

- Append-only. Never UPDATE / DELETE — `immutable_hash` is the integrity guarantee.
- Distinct from [agent_events](agent_events.md): `events` is user-facing activity feed; `agent_events` is per-agent-run audit trail.
