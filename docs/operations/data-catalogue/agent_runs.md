---
tags: [area/operations, data-catalogue]
---

# agent_runs

[← Data Catalogue](README.md) · [Lineage](../data-lineage/agent_runs.md) · Layer 5 — Agent audit

Run-level summary. One row per run, keyed by `run_id`. Inserted with `status='running'` at the top of a run and updated in place at run end with totals, summary, and cost rollup. Joined to [agent_events](agent_events.md) (the per-event trail) via `run_id`. See [docs/agents/system/agent-audit.md](../../agents/system/agent-audit.md) for the full audit pattern.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| run_id | text | PK | | |
| agent_id | text | no | | `scout`, `scribe`, `analyst`, `stats`, `fixtures` |
| agent_name | text | no | | |
| status | text | no | `running` | `running`, `completed`, `aborted`, `failed` |
| started_at | timestamptz | no | now() | |
| ended_at | timestamptz | yes | | |
| model | text | yes | | Claude model id |
| brief_preview | text | yes | | First N chars of the run brief |
| bounds_json | jsonb | no | {} | Run bounds (max turns, budget) |
| summary | text | no | "" | Filled at run end |
| detail_json | jsonb | no | {} | |
| s3_log_key | text | yes | | S3 key for the JSONL event upload |
| agent_events_count | int | yes | | Total events written to `agent_events` |
| turns_used | int | yes | | |
| tool_calls | int | yes | | |
| input_tokens | int | yes | | |
| output_tokens | int | yes | | |
| cache_read_tokens | int | yes | | |
| cache_write_tokens | int | yes | | |
| token_cost_usd | numeric(12,6) | yes | | Estimated, not invoiced |
| server_tool_cost_usd | numeric(12,6) | yes | | |
| total_cost_usd | numeric(12,6) | yes | | |

**Indexes:** (agent_id, started_at DESC), started_at DESC, started_at DESC WHERE status='running' (partial)

Token columns are rolled up from `agent_events.payload->'usage'`. Cost columns are estimated via `jeromelu_shared.agent_audit.estimate_*` — used for budget gates and observability, not invoicing.
