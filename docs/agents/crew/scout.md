---
tags: [area/agents, subarea/crew]
---

# Scout — Jaromelu's Inventory Mode

**Role:** Acquire and maintain the raw NRL media inventory across every supported platform. **Scout is the *Extract* in the system's ETL** — it pulls raw bytes from external sources and persists them as-is. **It does no Transformation** (no cleaning, parsing, diarisation, embedding, normalisation, or interpretation). Those are downstream agents.

Scope is everything from *we don't know about this source* to *raw transcripts persisted in the database*. Stops at the raw layer.

**Not a separate visible character.** When this mode is active, Jaromelu's voice (and the UI activity status) reflects it. Scout files inventory reports only — claims, contradictions, calls are all downstream.

|                       |                                                                                                                                                              |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Type**              | Crew mode (internal reasoning)                                                                                                                               |
| **ETL role**          | **Extract only.** No Transform. (Cleaning, diarisation, parsing, embedding, normalisation are all downstream.)                                               |
| **Scope**             | Discovery · post-approval enumeration · metadata refresh · raw transcript pull                                                                               |
| **Status**            | **Shipped:** agentic discovery, recon API, post-approval enumeration, weekly video-stats refresh. **In design:** deterministic discovery surface.            |
| **Platform coverage** | YouTube only today. Schema (`scout_candidates.platform`, `sources.platform`) is platform-agnostic; podcasts (RSS), Twitter/X, blogs, and Reddit are backlog. |
| **Code**              | `services/api/app/scout/` (discovery agent), `services/worker-ingestion/` (transcript pull)                                                                  |
| **Trigger**           | Manual CLI: `python -m app.scout.cli`. Scheduled runs and live SSE stream are planned.                                                                       |
| **Model**             | `claude-sonnet-4-6` via Claude Agent SDK (agentic surface only)                                                                                              |
| **Audit**             | `agent_runs` + `agent_events` + S3 JSONL, `agent_id='scout'` ([pattern](../system/agent-audit.md))                                                           |
| **Spec**              | [Source discovery](../system/source-discovery.md), [Ingestion](../system/ingestion.md)                                                                       |

---

## Pipeline position

Scout is the **inventory stage** of a multi-agent pipeline. It owns everything from "we don't know about this source" through "raw transcripts in the database." Parsing, scoring, numbers, and synthesis are downstream.

```
Scout       →  Analyst    →  Bookkeeper + Critic  →  Jaromelu
(this:         (extract)     (numbers + challenge)   (voice)
 inventory)
```

| Stage | Crew mode | System agent | What it does | Status |
|---|---|---|---|---|
| **Acquire** | **Scout** *(this doc)* | [source-discovery](../system/source-discovery.md), [ingestion](../system/ingestion.md) | Discover sources, enumerate their content, refresh metadata, pull transcripts | Shipped (YouTube only) |
| Extract | [Analyst](analyst.md) | [extraction](../system/extraction.md) (today via [Transcript Pipeline skill](../skills/transcript-pipeline.md)) | Turn raw content into entities, quotes, claims; cross-reference for contradictions | Skill-based today; worker not built |
| Decide | [Bookkeeper](bookkeeper.md) + [Critic](critic.md) | [decision](../system/decision.md), [scraper](../system/scraper.md) (SuperCoach + fixtures) | Acquire and apply numbers (breakevens, cap, fixtures), rank, challenge thin evidence | Scraper partial; decision worker not built |
| Voice | [Jaromelu](jaromelu.md) | [publishing](../system/publishing.md) | Integrate everything, commit to a call, publish in the on-screen voice | Live |

### What Scout DOES cover

1. **Discovering new channels** across platforms — deterministic YouTube-native search (§3.1, in design) for the bulk case; agentic web hunt today (§3.2, shipped) for off-platform / long-tail. YouTube only today; podcasts / Twitter / blogs / Reddit on backlog.
2. **Enumerating new sources from approved channels** — synchronous uploads-playlist walk on approval (§3.3, shipped) plus incremental weekly enumeration of fresh uploads on tracked channels (§3.4, shipped).
3. **Refreshing per-video metadata** — weekly snapshot of views / likes / comments into `video_metrics` (§3.4, shipped). Enables view-velocity ranking and breakout detection.
4. **Extracting raw content (transcripts)** — `IntelSweepWorkflow` pulls YouTube transcripts and chunks them into `source_chunks` (§3.5, dev-only). Production rebuild as cron-driven Python is planned.
5. **Refreshing channel-level metadata** — sub count, total views, video count, name changes, active/inactive detection. *Planned* — currently `channel_metrics` is only written at approval time, not periodically refreshed.
6. **Source health / liveness monitoring** — detecting stalled channels, 404 sources, transcript fetch failures, caption regenerations. *Backlog* — not built.
7. **Multi-platform expansion** — instantiate the same shape (discovery → approval → enumerate → refresh → extract) for podcasts (RSS), Twitter/X, blogs/news, Reddit. *Backlog* — schema is platform-agnostic; code is YouTube-only.

### What Scout DOES NOT cover

Per the **Extract-only** rule, anything that interprets, structures, or enriches the raw bytes is downstream:

- **Transcript cleaning** — fixing mangled player names, garbled words, auto-caption errors. Scout writes `raw_text`; the cleaning pass writes `cleaned_text` / `clean_text`. Owned by the [transcript pipeline](../skills/transcript-pipeline.md) / [Analyst](analyst.md).
- **Diarisation** — speaker turn detection, populating `source_speakers`. Owned by the content-production / Deepgram pipeline downstream of Scout.
- **Embedding** — `source_chunks.embedding`, `knowledge_base.embedding`. Owned by the indexer.
- **Semantic chapters** (`source_chapters`) — produced by the analyse-transcript pipeline to scope claim extraction.
- **Annotations** (`source_annotations`) — sentiment, sub-topic tags, entity mentions, themes.
- **Parsing content for meaning** — entity extraction, claim detection, quote pulls. That's [Analyst](analyst.md) ([extraction](../system/extraction.md)).
- **Cross-source consensus or contradiction detection** — Scout reports "5 sources covered the trade"; Analyst reports "4 say sell, 1 says hold."
- **Numeric NRL data** — SuperCoach scores/prices/breakevens, fixtures, match results. The crew split is *text inventory* (Scout) vs *numeric inventory* ([Bookkeeper](bookkeeper.md) via [scraper](../system/scraper.md)).
- **Player roster registry / SCD-2 attribute tracking** — that's [player-roster](../system/player-roster.md), feeding the entity layer Analyst uses.

### Hand-off contract

Scout's outputs are raw inventory rows only — Extract + Load, never Transform. The full chain Scout owns is `scout_candidates → channels → sources → source_documents → source_chunks`, plus the time-series metadata snapshots.

| Table | What Scout writes | What Scout does **not** write (filled in by Transform) |
|---|---|---|
| `scout_candidates` | Full row at discovery (kind, title, score, content_categories, score_reasons, run_id, `status='pending'`) | — |
| `channels` | Full row at approval | — |
| `sources` | Full row at enumeration (`source_type`, title, canonical_url, `approved_flag=true`, `ingestion_status='pending'`) | — |
| `source_documents` | `s3_key`, `raw_text`, `transcript_available`, `language`, `checksum`, `chunk_count` | `cleaned_text` (Transform: cleaning pass) |
| `source_chunks` | `raw_text`, `chunk_index`, `start_offset`, `end_offset`, `start_ts`, `end_ts` (preserves original caption boundaries) | `clean_text`, `embedding` (Transform: cleaning + embedding) |
| `channel_metrics` / `video_metrics` | Full row per snapshot | — |

Scout writes **nothing** to `source_speakers` (diarisation), `source_chapters` (semantic chapters), `source_annotations` (sentiment, mentions, themes), `quotes`, `claims`, `claim_chunks`, or any reasoning/output table. If a Scout-voiced UI line mentions parsed content (e.g. *"deep dive on Munster"*), that content was generated by a downstream agent and is being *surfaced through* Scout's voice mode — not produced by Scout itself.

---

## 1. Voice & Behaviour

**Tonal mode:** Tireless, efficient, nose-to-the-ground. Inventory reporting only — Scout files what was *found*, not what it *means*.

In Scout mode, Jaromelu's voice:
- reports inventory without editorialising — counts of new sources, new uploads, dedupe results
- surfaces volume and novelty at the **source / artefact** level ("4 new episodes", "1 new channel surfaced")
- flags discovery edge-cases ("nothing new since last sweep", "noisy sweep — most results were already-known")
- never parses content, infers themes, detects contradictions, or makes calls — those are [Analyst](analyst.md), [Critic](critic.md), and [Jaromelu](jaromelu.md)'s jobs
- defers any "what was said" claim to downstream agents, even when surfaced through Scout's voice

### Sample lines

These surface as Jaromelu-authored cards with internal mode = Scout. They report **inventory only** — no parsed content:

> "4 new episodes overnight on tracked channels. Indexing now."

> "KingOfSC just dropped a new video. Queued for transcript pull."

> "Nothing new since last sweep. The ecosystem is quiet."

> "3 new channels surfaced this week, 2 already in the dedupe set — 1 worth a closer look."

> "Found a new pod worth tracking — 'Tackles and Tinnies', three episodes deep."

**Out-of-mode lines** (these *look* like Scout but are downstream agents speaking through the same voice frame):

> ~~"4 new episodes overnight. 2 mention Cleary, 1 has a deep dive on Munster."~~ — *parsed content; this is [Analyst](analyst.md).*

> ~~"3 sources are talking about the same trade. That's unusual."~~ — *consensus detection; this is [Analyst](analyst.md).*

---

## 2. Flow

The full Scout function decomposes into two phases joined by a human-approval gate. The two phases answer two unrelated questions, so each gets its own diagram.

All current components are YouTube-only. Multi-platform expansion (podcasts, Twitter, blogs, Reddit) is roadmap — see §4. The diagrams below describe the YouTube path; each platform added later will instantiate the same shape (discovery surface → approval → enumerate → refresh → extract).

The architectural intent for the discovery phase is **deterministic-first for the bulk case, LLM for the long tail**:
- **Deterministic discovery** *(in design)* owns the cheap, fast, reproducible work: YouTube-native search and related-channel walks against a fixed seed-query bank, with server-side filtering against known IDs.
- **Agentic discovery** *(shipped)* owns what the LLM is uniquely good at: off-platform reach (blog / news / Reddit mentions YouTube doesn't see), semantic quality filtering, and coverage-gap targeting.

Both surfaces file into the same `scout_candidates` table. Human approval is the seam where LLM judgement stops and idempotent pipelines take over.

### 2.1 Discovery — *how do candidates land in `scout_candidates`?*

```mermaid
flowchart LR
    YT(["YouTube Data API"])
    Web(["Web<br/>blogs · news · Reddit"])

    subgraph Det["Deterministic surface — in design"]
      DetJob["§3.1<br/>youtube_search<br/>find_related_channels<br/><i>filter_known=True</i>"]
    end

    subgraph Ag["Agentic surface — shipped"]
      AgJob["§3.2<br/>Scout LLM loop<br/>web_search · web_fetch<br/>dedupe_check_bulk"]
    end

    Pending[("scout_candidates<br/>status='pending'")]
    Approve{{"§recon API<br/>human approval"}}

    DetJob <--> YT
    AgJob <--> Web
    DetJob -->|"persist (det)"| Pending
    AgJob  -->|"persist_candidate"| Pending
    Pending --> Approve

    classDef proposed stroke-dasharray: 5 5,stroke:#888
    class Det,DetJob proposed
```

**Legend:** rounded ovals = external systems · cylinders = DB tables · hexagon = human gate · dashed = in design.

**Trace:**
1. **Daily deterministic sweep** (§3.1, in design) — cron runs `youtube_search` over the seed-query bank and `find_related_channels` over every tracked channel. `filter_known=True` means the API call returns only novel IDs. Results persist with `discovered_via='youtube_search' | 'related_channels'`.
2. **Weekly agentic sweep** (§3.2) — Scout LLM loop runs on a slower cadence with a brief that says *"deterministic covers YouTube-native; your job is off-platform reach and the long tail."* Uses `web_search` for blog/news/Reddit mentions, `web_fetch` to read About pages and judge quality, persists what survives.
3. **Human reviews** — admin lists pending candidates via the recon API (regardless of source) and approves or rejects.

**Today vs target:**

| Aspect | Today (shipped) | Target (after deterministic surface lands) |
|---|---|---|
| Bulk YouTube discovery | LLM with `web_search` (slow, expensive) | YouTube API (sub-second, ~$0) |
| Adjacency expansion | LLM intuition | `find_related_channels` (deterministic) |
| Off-platform mentions | LLM with `web_search` | LLM with `web_search` (unchanged) |
| Semantic quality filter | LLM (during search) | LLM (focused, on a smaller candidate set) |
| Cost / run | ~$0.40–$1.00 per agentic run | ~$0 deterministic + ~$0.20 weekly LLM |
| Cadence | Manual CLI | Daily deterministic + weekly LLM |

### 2.2 Tracked-source operations — *how do we keep approved sources current and extract their content?*

```mermaid
flowchart LR
    Approve{{"approval<br/>(from §2.1)"}}
    YT(["YouTube Data API"])

    subgraph Sync["Synchronous — on approval"]
      Enum["§3.3<br/>refresh_channel_videos<br/>uploads-playlist walk"]
    end

    subgraph Weekly["Weekly — Mon 09:00 AET"]
      Refresh["§3.4<br/>refresh-videos endpoint<br/>incremental enumerate + stats"]
    end

    subgraph Dev["Dev only — Temporal"]
      Sweep["§3.5<br/>IntelSweepWorkflow<br/>transcript pull"]
    end

    Channels[("channels")]
    Sources[("sources")]
    VM[("video_metrics")]
    Chunks[("source_chunks")]

    Approve --> Channels
    Approve --> Enum
    Enum  <--> YT
    Enum  --> Sources
    Enum  --> VM
    Refresh <--> YT
    Refresh --> Sources
    Refresh --> VM
    Sources --> Sweep
    Sweep   --> Chunks
```

**Legend:** rounded ovals = external systems · cylinders = DB tables · hexagon = upstream gate · subgraphs = cadence (sync / weekly / dev-only).

**Trace:**
1. **Sync enumeration** (§3.3) — recon-approval handler commits `channels`, then synchronously calls `refresh_channel_videos(full_backfill=True)`. The channel's uploads playlist is walked (capped 200), each video inserted as a `sources` row, and a discovery-time `video_metrics` snapshot is written per video.
2. **Weekly cron keeps things current** (§3.4) — `POST /admin/scout/refresh-videos` walks each channel for new uploads using the last known `video_id` as cursor (typically 1 quota unit / channel / week) and re-snapshots stats for every YouTube source. ~750 quota units / pass.
3. **Transcripts get pulled** (§3.5) — `IntelSweepWorkflow` (Temporal, dev-only) fetches and chunks transcripts for new `sources` rows into `source_chunks`. Production rebuild as a cron-driven Python job is on the roadmap.

---

## 3. Components

Each component follows the same internal structure — trigger, inputs, processing, outputs, audit — so the five are directly comparable. Components are listed **deterministic-first** to reflect architectural intent (the deterministic surface owns the bulk; the agentic surface is the long-tail layer once both ship), not current build status.

### 3.1 Deterministic discovery `[deterministic, in design]`

Cheap, fast, reproducible YouTube-native discovery. Owns the bulk case (new uploads, adjacent channels) so the agentic surface is freed for off-platform and semantic work. Not yet built — design intent recorded here.

**Trigger** — Daily cron (proposed: 06:00 AET to land before morning content windows).

**Inputs**
- Seed query bank (versioned config) — broad NRL terms ("NRL podcast", "supercoach analysis", "NRLW review", "Cowboys breakdown", etc.)
- Every active channel in `channels` (for related-channel walks)
- YouTube Data API key
- Read-side: `channels.external_id`, `sources.canonical_url`, `scout_candidates.(platform,kind,external_id)` for the server-side filter

**Processing**
1. **`youtube_search(query, filter_known=True)`** — for each seed query, calls `search.list?type=channel,video&regionCode=AU`. Implementation filters returned IDs against the known-set in-process *before* returning to the caller. The agent / persist layer never sees a known result.
2. **`find_related_channels(known_channel_id, limit=10)`** — for each tracked channel, pulls related channels via YouTube's "channels related to" signal (or scrapes the channel's featured-channels surface as fallback). Filters known.
3. Persists novel results directly to `scout_candidates` with `status='pending'` and `discovered_via='youtube_search' | 'related_channels'`. Idempotent on `(platform, kind, external_id)`.

**Outputs** — rows in `scout_candidates` (same table as §3.2, distinguished by `discovered_via`). No score / content_categories on first pass — those are added post-hoc by a lightweight scoring pass (could be deterministic heuristics or a small LLM batch).

**Quota budget** — `search.list` = 100 units/call. ~10 seed queries × daily = 7,000 units/week. ~150 channels × `channels.list?relatedToChannelId` = depends on endpoint cost (verify during implementation). Target: stay within 10,000-unit/day free tier including the weekly refresh job (§3.4, ~750 units/week).

**Audit** — needs to land on `agent_runs` even though there's no LLM (treat the cron run as an "agent" of `agent_id='scout-det'` for unified cost/health dashboards). Open question — see roadmap row.

### 3.2 Discovery agent `[agentic]`

The web-hunting LLM loop. Files candidate channels and videos to `scout_candidates`. Today this is the *only* discovery surface; once the deterministic surface (§3.1) ships, it becomes the long-tail / off-platform surface.

**Trigger** — Manual CLI: `python -m app.scout.cli` (flags: `--dry-run`, `--max-turns`, `--budget`, `--brief`). Scheduled runs are planned.

**Inputs**
- System prompt (cacheable, ~1.1k tokens) — Scout voice + scope + tagging taxonomy
- Per-run user brief carrying the **anti-rediscovery known-set** (every tracked channel + every previously-surfaced candidate, with "search adjacent" instruction)
- Bounds: 20 turns, 60 tool calls, 900s wall-clock, $1 budget
- Tools:

| Tool | Type | Use |
|---|---|---|
| `web_search` | Anthropic built-in (`web_search_20250305`) | NRL queries, AU geo bias |
| `web_fetch` | Anthropic built-in (`web_fetch_20250209`) | Drill into a channel/video page |
| `dedupe_check_bulk` | Custom | Batched front-door firewall against `channels` / `sources` / `scout_candidates` |
| `dedupe_check` | Custom | Single-item variant for one-off investigations |
| `persist_candidate` | Custom | Idempotent INSERT into `scout_candidates` (`status='pending'`) |

**Processing** — multi-turn streaming loop in `services/api/app/scout/loop.py`. Each turn: assistant emits text + tool calls; client-side handlers run dedupe / persist; server-side tools execute on Anthropic's side. Loop ends on `end_turn` or first bound hit.

**Outputs** — rows in `scout_candidates` (kind, title, score, content_categories, score_reasons, run_id, `status='pending'`, `discovered_via='web_search'`). Console theatre: per-turn text streamed live, one line per tool call.

**Audit** — full standard pattern (see [`agent-audit.md`](../system/agent-audit.md)):
- `agent_runs` — `started` and `completed`/`failed` rows joined on `run_id`. Cost, tokens, candidates filed, dupes skipped, S3 log key
- `agent_events` — forensic per-event trace (turn_started, text, tool_use, tool_result, server_block, turn_complete, bound_hit, error, run_ended). Live-readable mid-run
- S3 JSONL bundle — `agent-logs/scout/{YYYY}/{MM}/{DD}/{run_id}.jsonl` on `jeromelu-clean-documents`

### 3.3 Post-approval enumerator `[deterministic]`

Runs synchronously inside the recon-approval HTTP handler. Pulls a freshly-approved channel's full uploads playlist and snapshots metrics.

**Trigger** — admin approve action on a `scout_candidates` candidate of `kind='channel'`, via `app/routers/recon.py`.

**Inputs** — approved `channels` row, YouTube Data API key, `full_backfill=True`.

**Processing** — `refresh_channel_videos()`:
1. Walks the channel's uploads playlist (`UU` + last 22 chars of `UC...` channel id) via `playlistItems.list`. Newest first, capped 200. ~1 quota unit per page of 50.
2. Inserts each video as a `sources` row (`source_type='youtube'`, `approved_flag=true`, `ingestion_status='pending'`). Idempotent on `canonical_url`.
3. Calls `videos.list?part=statistics,contentDetails` (1 unit per 50 ids) and writes one `video_metrics` row per newly-inserted video as the discovery-time snapshot.

**Outputs** — `sources` rows (videos), `video_metrics` snapshot rows.

**Failure mode** — approval still commits if YouTube API fails; channel is in `channels`, admin can re-trigger via the weekly refresh endpoint.

**Audit** — currently logged through the recon endpoint's standard request log (no `agent_runs` row — this is a deterministic post-processing step, not an agent run).

### 3.4 Weekly refresh job `[deterministic]`

Keeps every tracked YouTube channel's video list and per-video popularity numbers current. Idempotent.

**Trigger** — `POST /api/admin/scout/refresh-videos` with `X-Admin-Key`. Optional `?skip_stats=true` or `?skip_enumerate=true`. Cron suggestion: Mon 09:00 AET.

**Inputs** — every active YouTube channel and source in the DB; YouTube Data API key.

**Processing** — two phases:
1. **Incremental enumerate** (`refresh_all_channels_incremental`) — for each active channel, find the most recent already-known `sources.canonical_url`, extract its `video_id`, pass as the `after_video_id` cursor to `playlistItems.list`. Walker stops on cursor — typical week is one page (1 quota unit) and zero new videos per channel.
2. **Stats refresh** (`refresh_all_video_stats`) — pulls every YouTube source, batches `videos.list` 50 ids at a time, appends one `video_metrics` row per video. ~1 quota unit per 50 videos.

**Outputs** — new `sources` rows for fresh uploads + new `video_metrics` rows. Total ~750 YouTube quota units per pass against a 10,000-unit free tier.

**Downstream** — once `video_metrics` has 2+ samples per video, view-velocity ranking becomes available (SQL in [the spec](../system/source-discovery.md#influence-ranking)).

**Gap** — channel-level metadata (`channel_metrics`: subs, total views, video count, name changes, active/inactive) is only written at *approval time* today. It does not get periodically refreshed. Weekly channel-stats refresh is on the roadmap.

**Audit** — endpoint return value reports counts; no `agent_runs` row.

### 3.5 Tracked-channel ingestion `[deterministic, dev-only]`

Pulls raw transcripts from already-approved channels' videos. **Extract only** — writes raw fields and preserves source structure; no cleaning, diarisation, embedding, or interpretation.

**Trigger** — `IntelSweepWorkflow` on Temporal worker (`services/worker-ingestion/`). Dev environment only.

**Processing** — for each new video on a tracked channel:
1. Fetch the auto-caption transcript (raw bytes from YouTube)
2. Persist the full transcript: write `source_documents` row with `s3_key`, `raw_text`, `transcript_available=true`, `language`, `checksum`, `chunk_count`
3. Split the transcript at the original YouTube caption boundaries and persist each segment: write `source_chunks` rows with `raw_text`, `chunk_index`, `start_offset`, `end_offset`, `start_ts`, `end_ts`

**Status** — Temporal-based; dev-only. Production rebuild as cron-driven Python is on the roadmap per the [no-Temporal-in-prod rule](../system/scraper.md#fixture--match--injury-sync-planned).

**Outputs** — `source_documents` row + N `source_chunks` rows per video. **Raw fields only** — `cleaned_text` / `clean_text` / `embedding` are left NULL for the cleaning and indexing passes downstream.

**Hand-off boundary** — once `source_documents.transcript_available=true` and `source_chunks` rows exist for a source, Scout's job is done. The cleaning pass (Transform), diarisation pass (`source_speakers`), embedding pass (`source_chunks.embedding`), and claim extraction (`claims`) are all downstream and may run in any order.

---

## 4. Roadmap

Grouped by theme. Status labels:
- **Shipped** — live in production or dev (per §3 component status)
- **In design** — specced; implementation not started
- **Planned** — committed scope; no design yet
- **Backlog** — deferred or candidate; no commitment

### YouTube — depth on the existing platform

| Capability | Status | Notes |
|---|---|---|
| **Deterministic discovery surface (§3.1)** — `youtube_search` + `find_related_channels` with server-side `filter_known=True` | In design | Spec recorded in §3.1. Promotes the former "Tier 2" to a first-class architectural change. |
| Refocus agentic Scout brief on off-platform + long-tail (instead of competing with deterministic) | Planned | Tied to §3.1 landing |
| Admin review queue UI at `/admin/recon` | In design | Backend endpoints shipped; UI not started |
| Live Recon SSE stream in `/pulse` (theatric reasoning visible to users) | Planned | Drives the visible-reasoning UX |
| `Event` rows for the reasoning trace (Pulse feed integration) | Backlog | TBD when live stream lands |
| Scheduled Scout runs (cron / APScheduler) for the agentic surface | Planned | Manual CLI only today |
| **Weekly channel-metadata refresh** — periodic re-snapshot of subs/views/video count and active/inactive detection (extends §3.4) | Planned | Channel metadata only written at approval today |
| **Source health / liveness monitoring** — detect stalled channels, 404 sources, transcript fetch failures, caption regenerations | Backlog | Not built |
| Transcript-ingestion automation for newly-enumerated videos | Backlog | Videos land `ingestion_status='pending'`; `make prod-ingest` still manual per video |
| Production ingestion off Temporal | Planned | `IntelSweepWorkflow` is dev-only; rebuild as cron-driven Python per the [no-Temporal-in-prod rule](../system/scraper.md#fixture--match--injury-sync-planned) |
| `agent_runs` rows for deterministic jobs (3.2, 3.3, 3.4) | Backlog | Currently logged as plain HTTP requests / cron output; standardising would unify cost/health dashboards across agentic + deterministic components |

### Multi-platform expansion

Schema (`platform` field on `scout_candidates` / `sources`) is already platform-agnostic. Each new platform instantiates the same shape: discovery surface (det + agentic) → approval → enumerate → refresh → extract. **All entries below are Backlog** until cross-platform identity (§5) is decided.

| Platform | Discovery surface | Content extraction | Notes |
|---|---|---|---|
| **Podcasts** (Apple Podcasts / Spotify) | RSS catalogue search + `find_related` from tracked feeds | RSS feed enumeration → episode mp3 → transcribe (Deepgram?) | Closest analogue to YouTube. RSS makes `filter_known` trivial. |
| **Twitter / X** (NRL personalities) | Manual seed list + agentic for adjacent accounts | API or scrape; tweets become `source_chunks` directly (no transcription) | Quote-extraction value high, signal-to-noise low. |
| **Blogs / news** (Roar, NRL.com features, club sites) | RSS where available + agentic web search for new outlets | RSS enumerate → article HTML → readability extract | Off-platform discovery already works for these via §3.2; missing piece is structured ingestion. |
| **Reddit** (r/nrl, club subs) | API search for high-engagement threads, weekly | Thread + top comments to `source_chunks` | Community signal; complements expert-driven sources. |

---

## 5. Future improvements

Additive — they layer on top of Tier 1 (already built: known-set injection + bulk dedupe) without replacing it.

> **Note:** The former "Tier 2 — YouTube-aware tools" entry has been promoted to a first-class architectural change — see §3.1 (in design) and the roadmap.

**Tier 3 — Coverage-gap biasing (agentic surface)**
- Pre-run, count `scout_candidates.content_categories` (and, post multi-platform, `platform`) to find underrepresented dimensions
- Inject "Coverage gaps:" paragraph into the user brief to bias the run
- Most useful once §3.1 lands and the agentic surface is dedicated to long-tail work. Becomes especially valuable when multi-platform lands and "underrepresented" is multi-axis (category × platform).

**Quality scoring on §3.1 candidates**
- Deterministic discovery has no semantic filter — it persists everything novel
- Options: lightweight heuristic scorer (sub count, upload frequency, channel age), or a small batch LLM pass that reads About pages for raw candidates and assigns score + content_categories
- Becomes important if §3.1 floods `scout_candidates` with low-signal results

**Cross-platform deduplication**
- Once multi-platform lands, the same person/show may appear on YouTube + podcast feed + Twitter. The `scout_candidates.platform` axis avoids accidental re-onboarding on the same platform but doesn't link them across platforms.
- Add a `source_identity` concept (or use `channels.canonical_handle` consistently) so an Analyst querying "what has Pat Souness said this week" pulls across all platforms a single creator publishes on.

---

## 6. Related

- [Crew Dynamics](dynamics.md) — Scout mode's place in Jaromelu's internal reasoning flow
- [Source discovery system spec](../system/source-discovery.md) — full architecture, schema, SQL recipes, CLI flags, audit-trail recipes
- [Ingestion system spec](../system/ingestion.md) — `IntelSweepWorkflow` and transcript pull
- [Agent audit pattern](../system/agent-audit.md) — `agent_runs` / `agent_events` / S3 conventions shared across all SDK agents
- [Publishing agent](../system/publishing.md) — how Scout's events surface in Jaromelu's voice
