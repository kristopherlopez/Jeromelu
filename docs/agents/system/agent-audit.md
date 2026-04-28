# Agent Audit — Standardised Logging Pattern

**Module:** `packages/shared/jeromelu_shared/agent_audit.py`
**Applies to:** every agent built on the Anthropic Messages API + custom-tool loop (Scout today; Analyst, Critic, Bookkeeper, Archivist when they arrive).
**Reference implementation:** `services/api/app/scout/loop.py`.

This is the contract every Claude-Agent-SDK-based agent in the system MUST follow. Uniform audit trail = uniform observability + uniform debugging + uniform cost tracking, with no per-agent reinvention.

---

## What every agent gets

Three layers, all joined by a single `run_id`:

| Layer | Where | Built for |
|---|---|---|
| **Run summary** | `agent_runs` (DB) — `started` row + `completed`/`failed` row, both with top-level `run_id` | "Did agent X run today, what was the outcome, what did it cost" |
| **Per-event trace** | `agent_events` (DB) — one row per event, queryable while the run is in progress; **plus** an at-end JSONL bundle uploaded to `s3://{settings.s3_agent_logs_bucket}/agent-logs/{agent_id}/{YYYY}/{MM}/{DD}/{run_id}.jsonl` | "Why did it skip that result? What did web_search return on turn 3?" — DB for live + ad-hoc queries; S3 for long-term forensics. |
| **Domain output** | Agent-specific tables (`discovered_sources` for Scout, `claims` for Analyst, etc.) tagged with `run_id` | "What did this run actually produce" |

All three tables expose `run_id` as a top-level indexed column, so cross-table queries are clean: `SELECT … FROM agent_runs JOIN agent_events USING (run_id, agent_id) …`.

No local files. The DB is the live store, S3 is the forensic archive. The S3 key is stamped into the end `agent_runs.detail_json.s3_log_key`, so a single SQL query gets you from "this run" to its bundle. DB write failures during a run are logged but don't abort — the in-memory buffer still flushes to S3 as the safety net.

---

## Required imports (every agent loop)

```python
from jeromelu_shared.agent_audit import (
    AgentAuditLog,
    AgentBounds,
    estimate_token_cost,
    make_run_id,
    record_agent_ended,
    record_agent_started,
)
from jeromelu_shared.config import settings
```

---

## Required event types

Every event is a row in `agent_events` (and a line in the at-end JSONL bundle).

| Event `type` | Fires | Payload fields |
|---|---|---|
| `run_started` | Once at start | `model`, `brief`, `bounds` |
| `turn_started` | Each turn | (turn is a column) |
| `text` | Each text block from the assistant | `text` |
| `tool_use` | Each client-side tool call | `name`, `id`, `input` |
| `tool_result` | After each client-side tool returns | `name`, `tool_use_id`, `result`, `is_error` |
| `server_block` | Each server-side block (web_search, web_fetch, their results, etc.) | `block_type`, `block` |
| `turn_complete` | Each turn end | `stop_reason`, `usage`, `message_id`, `model`, `latency_ms`, `tool_counts` |
| `bound_hit` | When a bound aborts the run | `bound`, `value` |
| `error` | API or tool exception | `where`, `message` |
| `run_ended` | Once at end | `status`, `summary` |

`agent_events` schema:
```
event_id  UUID  PK
run_id    TEXT
agent_id  TEXT
sequence  INT   (per-run, dense, 0-indexed)
t         TIMESTAMPTZ
type      TEXT
turn      INT   (nullable)
payload   JSONB
UNIQUE (run_id, sequence)
```

`run_id`, `agent_id`, `t`, `sequence`, `type`, and `turn` are stamped automatically. Everything else for an event lands in `payload`. Strings/dicts are auto-truncated to ~5KB to keep rows small. Typical 15-min run produces 100–300 rows / under 1MB total.

---

## Required `agent_runs` rows

Two rows per run, both with `agent_id` and a shared top-level `run_id`:

**Started:**
```json
{
  "run_id": "scout-20260427T103045-a1b2c3",
  "agent_id": "scout",
  "agent_name": "Scout",
  "activity_type": "started",
  "summary": "Scout run started — model=claude-sonnet-4-6, budget=$3.0",
  "detail_json": {
    "model": "...",
    "brief_preview": "<first 500 chars>",
    "bounds": {...}
  }
}
```

**Ended** (`activity_type` ∈ `{completed, failed}` — `aborted` runs map to `completed` with `detail_json.status='aborted'`):
```json
{
  "run_id": "scout-20260427T103045-a1b2c3",
  "activity_type": "completed",
  "summary": "<one-line human summary>",
  "detail_json": {
    "status": "completed|aborted|failed", "model": "...",
    "turns_used": ..., "tool_calls": ...,
    "input_tokens": ..., "output_tokens": ...,
    "cache_read_tokens": ..., "cache_write_tokens": ...,
    "estimated_cost_usd": ...,
    "stop_reason": "...",
    "notes": [...],
    "started_at": "...", "ended_at": "...",
    "s3_log_key": "agent-logs/scout/2026/04/27/scout-...jsonl",
    "s3_log_bucket": "jeromelu-clean-documents",
    "agent_events_count": 247,
    "web_searches": 13,
    "web_fetches": 2,
    "total_api_latency_ms": 82117,
    "token_cost_usd": 0.1011,
    "search_cost_usd": 0.1300,
    // ...plus agent-specific counters (e.g. candidates_filed, claims_extracted)
  }
}
```

---

## Adding audit to a new agent — skeleton

```python
# services/api/app/<agent_name>/loop.py
from dataclasses import asdict
from datetime import datetime, timezone
from jeromelu_shared.agent_audit import (
    AgentAuditLog, AgentBounds, estimate_token_cost,
    make_run_id, record_agent_started, record_agent_ended,
)
from jeromelu_shared.config import settings

AGENT_ID = "analyst"          # MUST be in CrewActivity check constraint
AGENT_NAME = "Analyst"

def run_analyst(session, *, brief=None, model="claude-sonnet-4-6",
                bounds: AgentBounds | None = None, dry_run=False):
    bounds = bounds or AgentBounds()
    run_id = make_run_id(AGENT_ID)
    audit = AgentAuditLog(
        session=session, agent_id=AGENT_ID, run_id=run_id,
        s3_bucket=settings.s3_agent_logs_bucket,
    )

    record_agent_started(session, agent_id=AGENT_ID, agent_name=AGENT_NAME,
                         run_id=run_id, model=model, brief=user_brief,
                         bounds=asdict(bounds))
    audit.run_started(model=model, brief=user_brief, bounds=asdict(bounds))

    # ... agent loop ...
    # Per turn: audit.turn_started(turn=N)
    # Per text block: audit.text(turn=N, text=...)
    # Per client tool: audit.tool_use(...) + audit.tool_result(...)
    # Per server block: audit.server_block(...)
    # End of turn: audit.turn_complete(turn=N, stop_reason=..., usage={...})
    # On bound hit: audit.bound_hit(bound="max_budget_usd", value=...)
    # On error: audit.error(where=..., message=...)

    summary = {...}     # agent-specific counters + the standard set
    audit.run_ended(status=status, summary=summary)
    s3_key = audit.flush_to_s3()

    record_agent_ended(session, agent_id=AGENT_ID, agent_name=AGENT_NAME,
                       run_id=run_id, status=status,
                       summary_text=f"...{AGENT_NAME} run ...",
                       detail={**summary, "model": model,
                               "s3_log_key": s3_key,
                               "s3_log_bucket": settings.s3_agent_logs_bucket if s3_key else None,
                               "agent_events_count": audit.event_count})
```

---

## Bounds — every agent uses `AgentBounds`

```python
@dataclass
class AgentBounds:
    max_turns: int = 20
    max_tool_calls: int = 60
    max_wall_seconds: int = 900       # 15 min
    max_budget_usd: float = 3.00
```

Override per-agent at the call site if a particular agent legitimately needs different caps; do NOT subclass with new bound names. If a new bound type is genuinely needed (e.g. `max_documents_processed`), add it to `AgentBounds` so it's available to everyone.

---

## Cost estimation

Two helpers, summed for the budget gate:

- **`estimate_token_cost(model, in, out, cache_read, cache_write)`** — pricing from `MODEL_PRICING` dict. Unknown model → falls back to Sonnet 4.6 pricing (so the budget gate still trips, you just pay rough).
- **`estimate_server_tool_cost({"web_search": n, "web_fetch": m})`** — pricing from `SERVER_TOOL_PRICING_USD`. Currently `web_search` is $0.01/call ($10/1k), `web_fetch` is token-only.

Server-side tools are billed separately from tokens — a typical Scout run does 5–15 web_searches = $0.05–$0.15 on top of token cost. Always combine both when gating against `bounds.max_budget_usd`. The shared module is the single source of truth; verify pricing against current Anthropic numbers when editing.

---

## Run id — `make_run_id(agent_id)`

Format: `{agent_id}-{YYYYMMDDTHHMMSS}-{6-char-nonce}`.
Example: `scout-20260427T103045-a1b2c3`.

The agent prefix lets you grep logs / S3 keys / DB rows by agent without parsing JSON. The timestamp keeps runs sortable by name. The nonce avoids collisions from same-second triggers.

---

## `agent_runs` CHECK constraint — gotcha for new agents

`agent_runs.agent_id` has a CHECK constraint enumerating allowed values (currently `scout`, `scribe`, `analyst`, `stats`, `fixtures`). When adding a new agent (e.g. `critic`, `bookkeeper`, `archivist`), **first ship a migration that extends the constraint**, otherwise `record_agent_started` will fail at INSERT time.

Migration template:
```sql
-- 0NN_extend_agent_runs_agent_ids.sql
ALTER TABLE agent_runs DROP CONSTRAINT ck_agent_runs_agent_id;
ALTER TABLE agent_runs ADD CONSTRAINT ck_agent_runs_agent_id
    CHECK (agent_id IN ('scout', 'scribe', 'analyst', 'stats', 'fixtures', 'critic'));
```

Update the matching `__table_args__` in `packages/shared/jeromelu_shared/db/models.py` in the same changeset.

---

## Following the trail

### Cross-agent run summary

```sql
-- Most recent runs across ALL agents, with status, cost, S3 bundle key
SELECT
  start_row.created_at                              AS started_at,
  start_row.agent_name,
  start_row.run_id,
  end_row.activity_type                             AS final_state,
  end_row.detail_json->>'status'                    AS status_detail,
  end_row.detail_json->>'estimated_cost_usd'        AS cost,
  end_row.detail_json->>'agent_events_count'        AS events,
  end_row.detail_json->>'s3_log_key'                AS s3_log_key
FROM agent_runs start_row
LEFT JOIN agent_runs end_row
  ON end_row.run_id = start_row.run_id
 AND end_row.activity_type IN ('completed', 'failed')
WHERE start_row.activity_type='started'
ORDER BY start_row.created_at DESC
LIMIT 50;

-- Cost per agent over the last 7 days
SELECT
  agent_id,
  count(*) AS runs,
  sum((detail_json->>'estimated_cost_usd')::numeric) AS spend_usd
FROM agent_runs
WHERE activity_type IN ('completed', 'failed')
  AND created_at > now() - interval '7 days'
GROUP BY agent_id
ORDER BY spend_usd DESC NULLS LAST;

-- Run summary + event count via a clean JOIN
SELECT ar.run_id, ar.activity_type, ar.summary, count(ae.event_id) AS events
FROM agent_runs ar
LEFT JOIN agent_events ae USING (run_id, agent_id)
WHERE ar.created_at > now() - interval '24 hours'
GROUP BY ar.run_id, ar.activity_type, ar.summary, ar.created_at
ORDER BY ar.created_at DESC;
```

### Live trace via `agent_events`

```sql
-- Replay one run in order
SELECT sequence, t, type, turn,
       payload->>'name'  AS tool_name,
       LEFT(payload::text, 200) AS preview
FROM agent_events
WHERE run_id = 'scout-20260427T103045-a1b2c3'
ORDER BY sequence;

-- Live tail while a run is in progress (poll this from another connection)
SELECT sequence, type, turn, payload->>'name' AS name
FROM agent_events
WHERE run_id = 'scout-20260427T103045-a1b2c3'
ORDER BY sequence DESC
LIMIT 10;

-- All web_search queries any agent ran today
SELECT t, agent_id, run_id, payload->'input'->>'query' AS query
FROM agent_events
WHERE type='tool_use'
  AND payload->>'name' = 'web_search'
  AND t > current_date
ORDER BY t DESC;

-- Errors across all agents in the last day
SELECT t, agent_id, run_id,
       payload->>'where'   AS location,
       payload->>'message' AS message
FROM agent_events
WHERE type='error'
  AND t > now() - interval '24 hours'
ORDER BY t DESC;
```

### S3 bundle (long-term forensics)

```bash
aws s3 cp s3://jeromelu-clean-documents/agent-logs/scout/2026/04/27/scout-...jsonl - | jq

# Just the candidates filed
aws s3 cp s3://.../scout-...jsonl - \
  | jq -c 'select(.type=="tool_use" and .payload.name=="persist_candidate") | .payload.input | {title, score}'
```

---

## Settings

| Setting | Default | Purpose |
|---|---|---|
| `s3_agent_logs_bucket` | `jeromelu-clean-documents` | Bucket for the at-end JSONL bundle. Override per-env via `S3_AGENT_LOGS_BUCKET` env var. |

If unset (or S3 unreachable in dev), `flush_to_s3()` silently no-ops and `agent_events` remains the source of truth — you lose long-term archival but live debugging is unaffected.

---

## Anti-patterns

1. **Don't write a per-agent audit module.** Use `AgentAuditLog` from the shared module. If you need a new event type, add it to `AgentAuditLog` so all agents get it.
2. **Don't define a per-agent `Bounds` dataclass with the same fields.** Use `AgentBounds`.
3. **Don't compute cost inline.** Use `estimate_token_cost` so the pricing table stays in one place.
4. **Don't invent a run_id format.** Use `make_run_id(agent_id)`.
5. **Don't write to a per-agent S3 prefix.** The `agent-logs/{agent_id}/...` layout is the standard.
6. **Don't write audit data to local files.** `agent_events` (DB) is the live store; S3 is the archive. No `data/agent-logs/` writes.
7. **Don't skip the CrewActivity start row.** Zero-candidate / failed runs are invisible without it. Always pair `record_agent_started` with `record_agent_ended` (in a try/finally if the loop can raise).
