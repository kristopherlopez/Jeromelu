---
tags: [area/operations, data-lineage]
---

# Lineage: agent_runs

[Schema: data-catalogue/agent_runs.md](../data-catalogue/agent_runs.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Every Claude-Agent-SDK agent run | — | **Primary** — one row per run |
| Deterministic Miner admin pipelines | — | **Primary** for cron/admin fetch health; `agent_id='miner'`, `detail_json.pipeline` names the module |

## Writer

`jeromelu_shared.agent_audit` — every Claude-Agent-SDK-based agent (Miner, Scribe, Analyst, Stats, Fixtures) calls `start_run()` at the top, which INSERTs a row with `status='running'`, then `end_run()` UPDATEs in place at run end with totals, summary, and cost rollup. Deterministic Miner admin pipelines use `services/api/app/miner/common/pipeline_run.py`, which wraps the same helpers with `model='deterministic'`, zero token/tool counts, and a stable `detail_json.pipeline`. Per [[project_agent_audit_pattern]].

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `run_id` | derived (uuid hex) | PK; passed to all events for join |
| `agent_id` | agent | `miner`, `scribe`, `analyst`, `stats`, `fixtures` |
| `agent_name` | agent | Human-readable variant |
| `status` | lifecycle | `running` → `completed`/`aborted`/`failed` |
| `started_at` | derived | DB default `now()` at start_run |
| `ended_at` | end_run | Set on terminal status |
| `model` | agent | Claude model id (e.g. `claude-opus-4-7`) |
| `brief_preview` | agent | First N chars of the run brief |
| `bounds_json` | agent | Run bounds (max turns, budget caps) |
| `summary` | end_run | Agent-written end-of-run summary |
| `detail_json` | end_run | Free-form (e.g. `s3_archive_key` for produced artefacts) |
| `s3_log_key` | end_run | S3 key for the JSONL event upload |
| `agent_events_count` | end_run | Total events written to `agent_events` (rolled up from per-event inserts) |
| `turns_used`, `tool_calls` | end_run | Counters from agent loop |
| `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens` | end_run | Rolled up from `agent_events.payload->'usage'` |
| `token_cost_usd`, `server_tool_cost_usd`, `total_cost_usd` | end_run | Estimated via `jeromelu_shared.agent_audit.estimate_*` |

## Notes

- Cost columns are estimated for budget gates and observability — not invoicing. Real cost comes from Anthropic's billing API.
- The matching event trail is in [agent_events](agent_events.md), joined via `run_id`.
- Per [[project_agent_audit_pattern]]: every agent has run_id / bounds / cost / 3-layer audit trail (live DB rows + S3 JSONL upload + per-event rows).
- YouTube refresh labels: `youtube-refresh-videos` for the daily enumerate+video-stats endpoint, `youtube-channel-videos` for approval-time or ad-hoc one-channel enumeration, and `youtube-channel-stats` for channel metrics refresh. The daily `youtube-refresh-videos` endpoint remains HTTP 200 for per-channel enumeration partial failures, but its `agent_runs.status` is `failed` and `detail_json` includes `partial_failure`, `channels_failed`, and sample `channel_errors`.
- Miner source health (`app.miner.source_health`) reads these YouTube pipeline rows to classify stale channel stats refreshes, stale video refreshes, and recent failed refresh/backfill attempts. Missing completed run rows are surfaced as `unknown`, never as healthy.
