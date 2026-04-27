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
| `dedupe_check` | Custom | Returns `{known: bool, where: 'channels'|'sources'|'discovered_sources', ...}`. Call before persisting. |
| `persist_candidate` | Custom | Writes to `discovered_sources` with `status='pending'`. Idempotent on `(platform, kind, external_id)`. |

## Bounds

Defaults (override via CLI flags or `ScoutBounds`):

- `max_turns=20`
- `max_tool_calls=60`
- `max_wall_seconds=900` (15 min)
- `max_budget_usd=3.00` — rough estimate from token usage

## DB interactions

- Reads: `channels.external_id`, `sources.canonical_url`, `discovered_sources.(platform,kind,external_id)` — all dedup checks.
- Writes: `discovered_sources` rows only. Status starts as `pending`.

Approval flow (writes to `channels` / `sources`) is a separate slice — no admin endpoint yet.

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
