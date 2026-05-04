---
tags: [area/agents, subarea/system, status/live]
---

# Source Discovery (Scout)

| | |
|---|---|
| **Package** | `services/api/app/scout/` |
| **Trigger** | Manual CLI for now (`python -m app.scout.cli`); admin endpoint + cron later |
| **Crew counterpart** | [Scout](../crew/scout.md) — this is Scout's source-discovery surface |
| **ETL role** | **Extract only.** No Transform. (Cleaning, diarisation, parsing, embedding are downstream — see [crew/scout.md § Hand-off contract](../crew/scout.md#hand-off-contract).) |
| **Status** | Discovery + admin recon API + post-approval video enumeration shipped |

Scout's "find new sources" job. An autonomous Anthropic agent that hunts the web for NRL YouTube channels and videos, scores them, and files them to `scout_candidates` for human review. **Not Temporal-based** — runs in-process, see [project-temporal-not-in-prod note](../../operations/aws-resource-inventory.md).

Approval of a channel candidate triggers deterministic post-processing: the channel's full uploads playlist is enumerated and each video is inserted as a `sources` row, with an initial popularity snapshot in `video_metrics`. A weekly refresh job re-walks each channel for new uploads and re-snapshots view/like/comment counts so we can rank videos by influence and detect breakouts. See [§ Post-approval video enumeration](#post-approval-video-enumeration) below.

### Extract-only boundary

Per Scout's [ETL role](../crew/scout.md), this surface only writes **raw inventory**:
- `scout_candidates` (full row at discovery)
- `channels` (full row at approval)
- `sources` (full row at enumeration; `ingestion_status='pending'`, `cleaned_text` left for Transform)
- `video_metrics` / `channel_metrics` (snapshots from API output)

It does not write `source_documents` (that's [ingestion](ingestion.md)), nor anything in the Transform layer — `cleaned_text`, `source_chunks.clean_text`/`embedding`, `source_speakers`, `source_chapters`, `source_annotations`, `quotes`, `claims`. If a feature would interpret, clean, normalise, or enrich the raw bytes, it does not belong in `services/api/app/scout/`.

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
              dedupe_check     → SELECT against channels / sources / scout_candidates
              persist_candidate → INSERT scout_candidates (status='pending')
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
| `app/scout/youtube_api.py` | YouTube Data API v3 client (search, channel stats, playlist enumeration, video stats) |
| `app/scout/refresh.py` | Post-approval video enumeration + weekly stats refresh (deterministic, not agent-driven) |
| `app/routers/recon.py` | Admin recon endpoints (list/approve/reject candidates) + the weekly refresh entry point |
| `packages/db/migrations/017_discovered_sources.sql` | Candidate inbox table (renamed to `scout_candidates` in mig 035) |
| `packages/db/migrations/023_channel_metrics.sql` | Time-series channel popularity (subs/views/videos) |
| `packages/db/migrations/024_video_metrics.sql` | Time-series video popularity (views/likes/comments) |

## Tool palette

| Tool | Type | What it does |
|---|---|---|
| `web_search` | Anthropic built-in (`web_search_20250305`) | NRL-relevant queries, AU geo bias. `max_uses=15` per run. |
| `web_fetch` | Anthropic built-in (`web_fetch_20250209`) | Drill into a channel/video page to confirm details. |
| `dedupe_check_bulk` | Custom | Batched dedupe: pass an array of `{kind, url}`, get a verdict for each in one call. **Preferred** for filtering a fresh search-result page. |
| `dedupe_check` | Custom | Single-item dedupe. Use only when investigating one candidate (e.g. after a `web_fetch`). |
| `persist_candidate` | Custom | Writes to `scout_candidates` with `status='pending'`. Idempotent on `(platform, kind, external_id)`. |

## Anti-rediscovery — Tier 1 (built)

The first version of Scout kept re-discovering the same popular channels because `web_search` is server-side and we couldn't filter results before the agent saw them. Tier 1 fixes this:

1. **Known-set injection** — at run-start, `summarise_known_sources(session)` builds a compact list of every YouTube channel Scout already tracks (`channels` table) plus every channel previously surfaced as a candidate (`scout_candidates`, any status). This list is prepended to the per-run user brief (NOT the system prompt — system stays cached) with the rule: *"do not search for these by name. Search adjacent."*
2. **`dedupe_check_bulk`** — a batched dedupe tool the agent calls once per search-result page, instead of one `dedupe_check` per candidate. Stops the agent from drilling into already-known URLs.

Together these turn dedupe from a *post-hoc filter* into a *front-door firewall*.

## Bounds

Defaults (override via CLI flags or `ScoutBounds`):

- `max_turns=20`
- `max_tool_calls=60`
- `max_wall_seconds=900` (15 min)
- `max_budget_usd=1.00` — rough estimate from token usage

## DB interactions

- Reads: `channels.external_id`, `sources.canonical_url`, `scout_candidates.(platform,kind,external_id)` — all dedup checks.
- Writes: `scout_candidates` rows (candidates), `crew_activity` rows (run-level start + end summaries — see Audit trail below).

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

### 3. `scout_candidates` (already documented above)

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
FROM scout_candidates
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
FROM scout_candidates
WHERE run_id = (SELECT run_id FROM scout_candidates
                ORDER BY discovered_at DESC LIMIT 1)
ORDER BY score DESC NULLS LAST;

-- Pending review queue
SELECT kind, title, score, content_categories, discovered_via
FROM scout_candidates
WHERE status='pending'
ORDER BY score DESC NULLS LAST, discovered_at DESC;
```

## Post-approval video enumeration

When a channel candidate is approved, the recon endpoint commits the `channels`
row, then synchronously calls `refresh_channel_videos(channel, full_backfill=True)`.
This:

1. Walks the channel's auto-generated **uploads playlist** (`UU` + last 22 chars
   of the `UC...` channel id) via `playlistItems.list`. Newest first, capped at
   200 by default. Cheap — 1 quota unit per page of 50.
2. Inserts each video as a `sources` row (`source_type='youtube'`,
   `approved_flag=true` since the parent channel is already approved,
   `ingestion_status='pending'`). Idempotent on `canonical_url`.
3. Calls `videos.list?part=statistics,contentDetails` (1 unit per 50 ids) and
   writes one `video_metrics` row per newly-inserted video as the
   discovery-time snapshot.

If the YouTube API call fails the approval still commits — the channel is in
the canonical tables, and the admin can re-trigger enumeration via the weekly
refresh endpoint (below).

## Weekly video refresh

A single admin endpoint runs both the incremental enumerate and the stats
refresh:

```
POST /api/admin/scout/refresh-videos
  ?skip_stats=true        # enumerate only
  ?skip_enumerate=true    # stats only
  Header: X-Admin-Key
```

The job is idempotent and does two things:

1. **Incremental enumerate** (`refresh_all_channels_incremental`) — for every
   `channel` where `platform='youtube'` and `active=true`, find the most
   recent already-known `sources.canonical_url`, extract its `video_id`, and
   pass that as the `after_video_id` cursor to `playlistItems.list`. The
   walker stops as soon as it sees the cursor, so most weeks this is one API
   page (1 quota unit) and zero new videos per channel.
2. **Stats refresh** (`refresh_all_video_stats`) — pulls every YouTube source,
   batches `videos.list` 50 ids at a time, and appends one `video_metrics`
   row per video. ~1 quota unit per 50 videos. ~150 channels × ~200 videos =
   ~600 quota units per pass.

Total weekly quota cost: ~750 units against a 10,000-unit daily free tier.

Wired to cron — see [Production schedule](#production-schedule) below.

## Daily channel stats refresh

Lightweight cousin of the weekly video refresh. Snapshots subscriber /
video / view counts for every active YouTube channel into
`channel_metrics`:

```
POST /api/admin/scout/refresh-channel-stats
  Header: X-Admin-Key
```

Or via Make: `make prod-refresh-channel-stats ADMIN_KEY=xxx`.

Backed by `refresh_all_channel_stats()` in `app/scout/refresh.py`. Walks
every `channel` where `platform='youtube'` and `active=true`, batches the
external_ids 50 at a time into `channels.list`, and writes one
`channel_metrics` row per channel using the canonical shape from migration
023 (`subscribers`, `videos`, `views`, `country`, `channel_published_at`).
Identity fields (`handle`, `avatar_url`) are also synced onto the
`channels` row when the API returns them.

**Quota:** 1 unit per 50 channels — 3 units per pass at the projected ~150
channel scale. Cheap enough to run daily (10,000 units/day on the free
tier). Decoupled from the weekly video refresh because per-video stats are
~200× more expensive and don't need daily cadence.

Wired to cron — see [Production schedule](#production-schedule) below.

## Production schedule

Both refreshes run on the Lightsail box via a checked-in cron file:

- **Schedule:** [`scripts/cron.d/jeromelu`](../../../scripts/cron.d/jeromelu)
  — daily channel-stats at 09:00 AEST (23:00 UTC), weekly videos Monday
  09:15 AEST (Sun 23:15 UTC). DST drifts the local hour to 10:00 / 10:15
  AEDT during summer; accepted.
- **Wrapper:** [`scripts/scout-refresh.sh`](../../../scripts/scout-refresh.sh)
  — sources `/opt/jeromelu/.env` for `ADMIN_KEY`, hits the API, appends
  status + body to `/var/log/jeromelu/scout-refresh.log`, exits non-zero
  on non-2xx so cron / monitoring can surface failures.
- **Install:** `lightsail-deploy.sh` runs `sudo install` on every deploy
  to sync the cron file into `/etc/cron.d/jeromelu`. Edit the source file
  in this repo and redeploy — never hand-edit on the box. The same cron
  file also schedules the nightly `pg-backup.sh` at 02:30 AEST.

To inspect: `ssh jeromelu-prod 'tail -n 50 /var/log/jeromelu/scout-refresh.log'`.

To trigger a one-off run by hand (e.g. after fixing a quota error):
`make prod-refresh-channel-stats ADMIN_KEY=xxx` or
`make prod-refresh-videos ADMIN_KEY=xxx`.

## Channel coverage audit

Per-channel funnel showing how far each channel's videos have travelled
through the pipeline — surfaces both ingestion gaps and downstream
processing dropoffs.

**UI:** dev-only at [http://localhost:3000/admin](http://localhost:3000/admin)
— "Channel Coverage" tab. Each row colours the downstream stage relative
to its parent (green ≥95%, yellow ≥50%, red below). Toggle "Only gaps" to
filter to channels where Tracked < Reported.

**Raw API:**

```
GET /api/admin/scout/channel-coverage
  ?only_gaps=true         # filter to channels where tracked < reported
```

(Read-only inspection endpoint — no admin key required, matching
`/admin/pipeline` and `/admin/sync-status`.)

**Make target** (prod, with key):
`make prod-channel-coverage ADMIN_KEY=xxx [ONLY_GAPS=1]`.

Backed by `audit_channel_coverage()` in `app/scout/refresh.py`. Per-channel
funnel stages — same vocabulary as `/admin/pipeline`:

| Column | Definition |
|---|---|
| `reported_videos`  | Latest `channel_metrics.metrics->>'videos'` — what YouTube reports |
| `tracked_videos`   | Rows in `sources` for the channel |
| `collected_videos` | Sources whose transcript has been saved (a `source_documents` row exists with `s3_key` or chunks) |
| `cleaned_videos`   | Sources with at least one `source_chunks.clean_text` populated |

Plus rollup totals (`channels_with_gap`, `total_gap`) where `gap = reported - tracked`. Pure DB read, no API quota cost.

Freshness of `reported_videos` depends on the
[daily channel stats refresh](#daily-channel-stats-refresh) cron keeping
`channel_metrics` current.

## Influence ranking

Once `video_metrics` has 2+ samples per video you can compute view-velocity:

```sql
-- Videos by week-over-week view delta, top 50
WITH latest AS (
  SELECT source_id, sampled_at, (metrics->>'views')::bigint AS views
  FROM video_latest_metrics
),
prior AS (
  SELECT DISTINCT ON (source_id)
    source_id,
    (metrics->>'views')::bigint AS views_prior
  FROM video_metrics
  WHERE sampled_at < now() - interval '5 days'
  ORDER BY source_id, sampled_at DESC
)
SELECT
  s.title,
  c.name AS channel_name,
  l.views AS views_now,
  l.views - COALESCE(p.views_prior, 0) AS view_delta_week,
  s.canonical_url
FROM latest l
JOIN sources s ON s.source_id = l.source_id
LEFT JOIN channels c ON c.channel_id = s.channel_id
LEFT JOIN prior p ON p.source_id = l.source_id
ORDER BY view_delta_week DESC NULLS LAST
LIMIT 50;
```

## What's not in Slice 2

- Admin review queue UI (`/admin/recon`) — backend endpoints exist; UI pending
- Live Recon stream in `/pulse` (SSE) — Slice 3
- Scheduled Scout runs (cron / APScheduler) — Slice 4
- `Event` rows for the agent's reasoning trace — TBD when the live stream lands
- Transcript-ingestion automation for newly-enumerated videos — single-source
  CLI shipped (`make extract-transcript SOURCE_ID=...`, audio-first via
  Deepgram — see [`ingestion.md`](ingestion.md) and
  [`sources/extraction-method.md`](../../sources/extraction-method.md)).
  Recurring drain over `ingestion_status='pending'` is the next slice.

## Future improvements — Tier 2 and Tier 3

Documented for when Tier 1 stops being enough.

### Tier 2 — Replace generic `web_search` with YouTube-aware tools

Tier 1 reduces wasted drill-ins but doesn't stop the upstream search engine from returning popular hits in the first place. Tier 2 cuts at the source.

Add two custom tools that replace generic `web_search` for YouTube-specific discovery:

- **`youtube_search(query, filter_known=True)`** — calls the YouTube Data API (or `yt-dlp --match-filter`) directly. Server-side filters out any channel/video whose `external_id` is already in `channels` / `sources` / `scout_candidates` *before* returning to the agent. The agent only ever sees novel results.
- **`find_related_channels(known_channel_id, limit=10)`** — pulls channels related to one we already track, via YouTube's "related channels" signal or by scraping the channel's collaborators / community / featured-channels surface. High-leverage for finding adjacent creators we don't already know.

Tradeoffs: more code, YouTube Data API quota to budget (search.list is 100 units/call vs the 10,000-unit daily free tier), and we lose some serendipity (`web_search` sometimes finds great channels via blog posts that mention them — a YouTube-native tool can't).

Keep `web_search` available but de-emphasise it in the prompt; use it for the off-platform discovery angle (blogs, news mentions) only.

### Tier 3 — Bias toward category gaps

Today the brief is even-handed across the full NRL ecosystem. In practice the agent will gravitate to whatever sub-vertical the search engine surfaces most — likely SuperCoach + match highlights, since those dominate volume.

Tier 3: pre-run, count `scout_candidates.content_categories` to find which tags are underrepresented (e.g. zero candidates for `nrlw`, `junior`, `classic`). Inject into the user brief:

```
Coverage gaps: nrlw (0 candidates), junior (0), classic (1).
This run: bias toward these.
```

Cheap to add (one query + one paragraph in the brief). Naturally rotates Scout through the long tail without us having to write rotating query banks. Best added once we have a few runs of data so "underrepresented" actually means something.

Both tiers are additive — they layer on top of Tier 1 without replacing it.
