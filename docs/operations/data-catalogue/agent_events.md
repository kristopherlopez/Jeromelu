---
tags: [area/operations, data-catalogue]
---

# agent_events

[← Data Catalogue](README.md) · [Lineage](../data-lineage/agent_events.md) · Layer 5 — Agent audit

Per-event audit trail. One row per event in an agent run; dense `sequence` per run for ordered replay. Joined to [agent_runs](agent_runs.md) via `run_id`.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| event_id | UUID | PK | uuid4 | |
| run_id | text | no | | Joins to `agent_runs.run_id` |
| agent_id | text | no | | |
| sequence | int | no | | 0-indexed, dense, per-run |
| t | timestamptz | no | now() | |
| type | text | no | | `run_started`, `turn_started`, `text`, `tool_use`, `tool_result`, `server_block`, `turn_complete`, `bound_hit`, `error`, `run_ended` |
| turn | int | yes | | NULL on lifecycle events (e.g. `run_started`) |
| payload | jsonb | no | {} | Type-specific payload (text body, tool input/output, usage, etc.) |

**Unique:** (run_id, sequence)
**Indexes:** (run_id, sequence), (agent_id, t DESC), type

Ten standard event types defined in `jeromelu_shared.agent_audit`.
