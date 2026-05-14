---
tags: [area/operations, data-lineage]
---

# Lineage: agent_events

[Schema: data-catalogue/agent_events.md](../data-catalogue/agent_events.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Same writers as [agent_runs](agent_runs.md) | — | One event row per agent loop event |

## Writer

`jeromelu_shared.agent_audit` — every event in an agent run (turn boundaries, text emissions, tool uses, tool results, usage updates, errors, lifecycle markers) calls `record_event()`, which INSERTs a row keyed on the run's `run_id` with a dense per-run `sequence`.

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `event_id` | derived | UUID, DB-side default |
| `run_id` | agent loop | Joins to `agent_runs.run_id` |
| `agent_id` | agent | Mirrors `agent_runs.agent_id` (denormalised for query convenience) |
| `sequence` | agent loop | 0-indexed, dense, per-run; UNIQUE with run_id |
| `t` | derived | Event timestamp; DB default `now()` |
| `type` | agent loop | `run_started`, `turn_started`, `text`, `tool_use`, `tool_result`, `server_block`, `turn_complete`, `bound_hit`, `error`, `run_ended` |
| `turn` | agent loop | NULL on lifecycle events (`run_started`, `run_ended`) |
| `payload` | agent loop | Type-specific (text body for `text`, tool input/output for `tool_use`/`tool_result`, usage stats for `turn_complete`, etc.) |

## Notes

- Ten standard event types defined in `jeromelu_shared.agent_audit`.
- The same events also serialise to JSONL and upload to S3 at run end (key in `agent_runs.s3_log_key`) for long-term forensics. The DB rows are for live-queryable observability; S3 is the durable audit copy.
- Token usage rollups in [agent_runs](agent_runs.md) are computed from `payload->'usage'` aggregates over these rows.
