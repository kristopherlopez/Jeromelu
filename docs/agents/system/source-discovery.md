# Source Discovery (Scout)

| | |
|---|---|
| **Package** | `services/api/app/scout/` |
| **Trigger** | Manual CLI for now (`python -m app.scout.cli`); admin endpoint + cron later |
| **Crew counterpart** | [Scout](../crew/scout.md) — this is Scout's source-discovery mode |
| **Status** | Slice 1 — discovery + persistence (no admin UI / live recon UI yet) |

Scout's "find new sources" job. An autonomous Anthropic agent that hunts the web for NRL YouTube channels and videos, scores them, and files them to `discovered_sources` for human review. **Not Temporal-based** — runs in-process, see [project-temporal-not-in-prod note](../../operations/aws-resource-inventory.md).

---

## Architecture

```
ANTHROPIC_API_KEY
        │
        ▼
  Anthropic Messages API ◀── Scout system prompt (cacheable, ~1.1k tokens)
        │                  ◀── Tools: web_search, web_fetch, dedupe_check, persist_candidate
        │                  ◀── User brief (NRL scope; can be overridden per run)
        ▼
  Multi-turn streaming loop  (services/api/app/scout/loop.py)
        │
        ├── text deltas → stdout (theatre)
        │
        ├── server-side tools (web_search, web_fetch) — executed by Anthropic
        │
        └── client-side tools — executed locally:
              dedupe_check     → SELECT against channels / sources / discovered_sources
              persist_candidate → INSERT discovered_sources (status='pending')
                                   ON CONFLICT DO NOTHING
        │
        ▼
  ScoutRunResult (turns, tool_calls, candidates_filed, tokens, est. cost)
```

## Files

| File | Purpose |
|---|---|
| `app/scout/prompt.py` | System prompt (Scout voice + scope + tagging taxonomy) and default user brief |
| `app/scout/tools.py` | Anthropic tool definitions + Python handlers (`dedupe_check`, `persist_candidate`) |
| `app/scout/loop.py` | Multi-turn streaming loop with bounds (turns, tool calls, wall-clock, USD budget) |
| `app/scout/cli.py` | `python -m app.scout.cli` entry point |
| `packages/db/migrations/017_discovered_sources.sql` | Candidate inbox table |

## Tool palette

| Tool | Type | What it does |
|---|---|---|
| `web_search` | Anthropic built-in (`web_search_20250305`) | NRL-relevant queries, AU geo bias. `max_uses=15` per run. |
| `web_fetch` | Anthropic built-in (`web_fetch_20250209`) | Drill into a channel/video page to confirm details. |
| `dedupe_check_bulk` | Custom | Batched dedupe: pass an array of `{kind, url}`, get a verdict for each in one call. **Preferred** for filtering a fresh search-result page. |
| `dedupe_check` | Custom | Single-item dedupe. Use only when investigating one candidate (e.g. after a `web_fetch`). |
| `persist_candidate` | Custom | Writes to `discovered_sources` with `status='pending'`. Idempotent on `(platform, kind, external_id)`. |

## Anti-rediscovery — Tier 1 (built)

The first version of Scout kept re-discovering the same popular channels because `web_search` is server-side and we couldn't filter results before the agent saw them. Tier 1 fixes this:

1. **Known-set injection** — at run-start, `summarise_known_sources(session)` builds a compact list of every YouTube channel Scout already tracks (`channels` table) plus every channel previously surfaced as a candidate (`discovered_sources`, any status). This list is prepended to the per-run user brief (NOT the system prompt — system stays cached) with the rule: *"do not search for these by name. Search adjacent."*
2. **`dedupe_check_bulk`** — a batched dedupe tool the agent calls once per search-result page, instead of one `dedupe_check` per candidate. Stops the agent from drilling into already-known URLs.

Together these turn dedupe from a *post-hoc filter* into a *front-door firewall*.

## Bounds

Defaults (override via CLI flags or `ScoutBounds`):

- `max_turns=20`
- `max_tool_calls=60`
- `max_wall_seconds=900` (15 min)
- `max_budget_usd=1.00` — rough estimate from token usage

## DB interactions

- Reads: `channels.external_id`, `sources.canonical_url`, `discovered_sources.(platform,kind,external_id)` — all dedup checks.
- Writes: `discovered_sources` rows (candidates), `crew_activity` rows (run-level start + end summaries — see Audit trail below).

Approval flow (writes to `channels` / `sources`) is a separate slice — no admin endpoint yet.

## Audit trail

Scout uses the standardised audit pattern that every Claude-Agent-SDK-based agent follows. Full pattern doc: [`agent-audit.md`](agent-audit.md). Scout-specific surface summarised below.

### 1. `agent_runs` — run-level summary (DB)

Two rows per run, both with `agent_id='scout'` and a shared top-level `run_id`. Joins cleanly to `agent_events` on `(run_id, agent_id)`.

**Started row** — written before the agent's first turn:

```json
{
  "agent_id": "scout",
  "agent_name": "Scout",
  "activity_type": "started",
  "summary": "Scout run started — model=claude-sonnet-4-6, budget=$3.0",
  "detail_json": {
    "run_id": "scout-20260427T103045-a1b2c3",
    "model": "claude-sonnet-4-6",
    "brief_preview": "<first 500 chars of the brief>",
    "bounds": {"max_turns": 20, "max_tool_calls": 60, ...}
  }
}
```

**Completed / failed row** — written at run end:

```json
{
  "activity_type": "completed",   // or "failed"
  "summary": "Scout run completed — 12 filed, 3 dupes, 8 turns, 24 tool calls, $0.428",
  "detail_json": {
    "run_id": "scout-20260427T103045-a1b2c3",
    "status": "completed",                // 'completed' | 'aborted' | 'failed'
    "turns_used": 8, "tool_calls": 24,
    "candidates_filed": 12, "duplicates_skipped": 3,
    "input_tokens": ..., "output_tokens": ...,
    "cache_read_tokens": ..., "cache_write_tokens": ...,
    "estimated_cost_usd": 0.4283,
    "stop_reason": "end_turn",
    "notes": [],
    "model": "claude-sonnet-4-6",
    "started_at": "...", "ended_at": "...",
    "s3_log_key": "scout-logs/2026/04/27/scout-20260427T103045-a1b2c3.jsonl",
    "s3_log_bucket": "jeromelu-clean-documents",
    "local_log_path": "data/scout-logs/scout-20260427T103045-a1b2c3.jsonl"
  }
}
```

`activity_type='completed'` covers both successful end_turn and bounds-aborted runs — drill into `detail_json.status` for the distinction (`completed` vs `aborted`). `activity_type='failed'` is reserved for API errors.

### 2. `agent_events` — per-event trace (DB) + S3 JSONL bundle

The forensic record. Each event becomes a row in `agent_events` as it happens (so you can `SELECT` from another connection while a run is in progress). At run end the buffered events are also uploaded to S3 as a single JSONL bundle for long-term archive.

S3 key format: `agent-logs/scout/{YYYY}/{MM}/{DD}/{run_id}.jsonl` on `s3_agent_logs_bucket` (defaults to `jeromelu-clean-documents`, prod-overridable).

No local files. DB is the live store, S3 is the archive.

Event types:

| `type` | Fires | Key fields |
|---|---|---|
| `run_started` | once at start | `model`, `brief`, `bounds` |
| `turn_started` | start of each turn | `turn` |
| `text` | per text block from the assistant | `turn`, `text` |
| `tool_use` | client-side tool call (dedupe / persist) | `turn`, `name`, `id`, `input` |
| `tool_result` | after our handler runs | `turn`, `name`, `tool_use_id`, `result`, `is_error` |
| `server_block` | server-side blocks (web_search, web_fetch, their results) | `turn`, `block_type`, `block` |
| `turn_complete` | end of each turn | `turn`, `stop_reason`, `usage` |
| `bound_hit` | when a bound aborts the run | `bound`, `value` |
| `error` | API or tool exception | `where`, `message` |
| `run_ended` | once at end | `status`, `summary` |

Every event has `t` (UTC ISO timestamp) and `run_id`. Large strings/dicts are truncated at 5–20KB to keep the log bounded; for a typical 15-min run expect 100–300 events / 50–500KB.

### 3. `discovered_sources` (already documented above)

Per-candidate record, joined to a run via `run_id`.

### Following the trail

```sql
-- Most recent Scout runs with status, cost, and S3 log location
SELECT
  start_row.created_at                              AS started_at,
  start_row.run_id,
  end_row.activity_type                             AS final_state,
  end_row.detail_json->>'status'                    AS status_detail,
  end_row.detail_json->>'candidates_filed'          AS filed,
  end_row.detail_json->>'duplicates_skipped'        AS dupes,
  end_row.detail_json->>'estimated_cost_usd'        AS cost,
  end_row.detail_json->>'s3_log_key'                AS s3_log_key
FROM agent_runs start_row
LEFT JOIN agent_runs end_row
  ON end_row.run_id = start_row.run_id
 AND end_row.activity_type IN ('completed', 'failed')
WHERE start_row.agent_id='scout' AND start_row.activity_type='started'
ORDER BY start_row.created_at DESC
LIMIT 20;

-- Candidates from one specific run
SELECT kind, title, score, content_categories, url
FROM discovered_sources
WHERE run_id = 'scout-20260427T103045-a1b2c3'
ORDER BY score DESC NULLS LAST;

-- Run summary + event count via clean JOIN
SELECT ar.run_id, ar.activity_type, ar.summary, count(ae.event_id) AS events
FROM agent_runs ar
LEFT JOIN agent_events ae USING (run_id, agent_id)
WHERE ar.agent_id='scout'
GROUP BY ar.run_id, ar.activity_type, ar.summary, ar.created_at
ORDER BY ar.created_at DESC LIMIT 10;
```

Reading the live trace:

```sql
-- All events from one Scout run, in order
SELECT sequence, t, type, turn,
       payload->>'name'  AS tool_name,
       LEFT(payload::text, 200) AS preview
FROM agent_events
WHERE run_id = 'scout-20260427T103045-a1b2c3'
ORDER BY sequence;

-- Just the candidates filed during this run
SELECT t, payload->'input' AS candidate
FROM agent_events
WHERE run_id = 'scout-20260427T103045-a1b2c3'
  AND type = 'tool_use'
  AND payload->>'name' = 'persist_candidate'
ORDER BY sequence;

-- Just Scout's narration (text blocks)
SELECT sequence, payload->>'text' AS text
FROM agent_events
WHERE run_id = 'scout-20260427T103045-a1b2c3'
  AND type = 'text'
ORDER BY sequence;
```

Reading the S3 bundle:

```bash
aws s3 cp s3://jeromelu-clean-documents/agent-logs/scout/2026/04/27/scout-20260427T103045-a1b2c3.jsonl - | jq
```

For cross-agent SQL (weekly spend, all errors today, etc.), see [`agent-audit.md`](agent-audit.md#following-the-trail).

## Running Slice 1

From `services/api` with venv active and `ANTHROPIC_API_KEY` exported:

```bash
# default — sonnet 4.6, 20 turns, $3 budget
python -m app.scout.cli

# safer first run
python -m app.scout.cli --dry-run

# tighter run for cost-watching
python -m app.scout.cli --max-turns 5 --budget 0.50

# narrow brief
python -m app.scout.cli --brief "Find injury-focused NRL podcasts only"
```

Console shows:
- The brief
- Per-turn assistant text streamed live
- One line per tool call (`[tool] web_search('NRL injury podcast')`)
- Truncated tool result for custom tools (`[tool-result] {...}`)
- Final summary: turns, tool calls, candidates filed, tokens, cost

## Inspecting results

Until the admin UI lands (later slice), use SQL:

```sql
-- Most recent run's candidates
SELECT kind, title, score, content_categories, url, score_reasons
FROM discovered_sources
WHERE run_id = (SELECT run_id FROM discovered_sources
                ORDER BY discovered_at DESC LIMIT 1)
ORDER BY score DESC NULLS LAST;

-- Pending review queue
SELECT kind, title, score, content_categories, discovered_via
FROM discovered_sources
WHERE status='pending'
ORDER BY score DESC NULLS LAST, discovered_at DESC;
```

## What's not in Slice 1

- Admin review queue UI (`/admin/recon`) — Slice 2
- Live Recon stream in `/pulse` (SSE) — Slice 3
- Scheduled runs (cron / APScheduler) — Slice 4
- `crew_activity` rows for run summaries — TBD when admin UI needs them
- `Event` rows for the agent's reasoning trace — TBD when the live stream lands
- Promotion endpoint (approve a candidate → write `Channel`/`Source` row) — Slice 2

## Future improvements — Tier 2 and Tier 3

Documented for when Tier 1 stops being enough.

### Tier 2 — Replace generic `web_search` with YouTube-aware tools

Tier 1 reduces wasted drill-ins but doesn't stop the upstream search engine from returning popular hits in the first place. Tier 2 cuts at the source.

Add two custom tools that replace generic `web_search` for YouTube-specific discovery:

- **`youtube_search(query, filter_known=True)`** — calls the YouTube Data API (or `yt-dlp --match-filter`) directly. Server-side filters out any channel/video whose `external_id` is already in `channels` / `sources` / `discovered_sources` *before* returning to the agent. The agent only ever sees novel results.
- **`find_related_channels(known_channel_id, limit=10)`** — pulls channels related to one we already track, via YouTube's "related channels" signal or by scraping the channel's collaborators / community / featured-channels surface. High-leverage for finding adjacent creators we don't already know.

Tradeoffs: more code, YouTube Data API quota to budget (search.list is 100 units/call vs the 10,000-unit daily free tier), and we lose some serendipity (`web_search` sometimes finds great channels via blog posts that mention them — a YouTube-native tool can't).

Keep `web_search` available but de-emphasise it in the prompt; use it for the off-platform discovery angle (blogs, news mentions) only.

### Tier 3 — Bias toward category gaps

Today the brief is even-handed across the full NRL ecosystem. In practice the agent will gravitate to whatever sub-vertical the search engine surfaces most — likely SuperCoach + match highlights, since those dominate volume.

Tier 3: pre-run, count `discovered_sources.content_categories` to find which tags are underrepresented (e.g. zero candidates for `nrlw`, `junior`, `classic`). Inject into the user brief:

```
Coverage gaps: nrlw (0 candidates), junior (0), classic (1).
This run: bias toward these.
```

Cheap to add (one query + one paragraph in the brief). Naturally rotates Scout through the long tail without us having to write rotating query banks. Best added once we have a few runs of data so "underrepresented" actually means something.

Both tiers are additive — they layer on top of Tier 1 without replacing it.
