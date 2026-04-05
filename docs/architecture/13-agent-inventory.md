# Agent Inventory

Complete inventory of all agents in the JeromeLu system. Covers Temporal workflow agents, LLM activity agents, and Claude Code skill agents.

For architectural intent see [05-runtime-architecture.md](05-runtime-architecture.md), [06-llm-architecture.md](06-llm-architecture.md), and [07-workflow-architecture.md](07-workflow-architecture.md).

---

## Temporal Orchestration Layer

All Temporal agents share infrastructure defined in `packages/shared/jeromelu_shared/temporal.py`, which provides task queue constants, a client factory, and deterministic workflow ID generation.

### Orchestrator

| | |
|---|---|
| **Worker** | `services/worker-orchestrator/app/main.py` |
| **Task Queue** | `orchestrator` |
| **Purpose** | Central hub that owns workflow definitions and coordinates distributed activity workers |
| **Status** | Skeleton — workflow list is empty; workflows currently registered directly by their activity workers |

The design intent (per `docs/todo/1_1_temporal_orchestration_setup.md`) is for all workflow definitions to live here, with activity workers registering only activities. This centralisation hasn't been completed yet.

---

### Workflow Agents

#### IntelSweepWorkflow

| | |
|---|---|
| **Worker** | `services/worker-ingestion/app/main.py` |
| **Workflow** | `services/worker-ingestion/app/workflows/intel_sweep.py` |
| **Task Queue** | `ingestion` |
| **Schedule** | Daily 10 PM AEST |
| **Purpose** | Content ingestion pipeline: discover new videos on whitelisted channels, fetch transcripts to S3, index Source + SourceDocument to DB |

**Steps:**
1. `discover_new_videos` — poll channels, deduplicate by watermark
2. For each new video:
   - `collect_transcript` — fetch via YouTube API, store JSON in S3
   - `index_document` — write Source + SourceDocument rows

**Retry policy:** 3 attempts, 5s initial interval, 2x backoff. Non-retryable: `RateLimitError`, `NoTranscriptFound`, `TranscriptsDisabled`.

**Returns:** `{discovered, collected, indexed, errors}`

---

#### FeedGenerationWorkflow

| | |
|---|---|
| **Worker** | `services/worker-publishing/app/main.py` |
| **Workflow** | `services/worker-publishing/app/workflows/feed_generation.py` |
| **Task Queue** | `publishing` |
| **Purpose** | Synthesise extracted claims into opinionated feed events in JeromeLu's voice |

**Steps (sequential):**
1. `fetch_unprocessed_claims` — find claims not yet linked to any Event
2. `update_consensus_snapshots` — compute consensus scores, detect sentiment flips
3. `generate_review_data` — compare past predictions against actual match outcomes
4. `generate_feed_events` — LLM synthesis (OpenAI gpt-4o, temp 0.2) with character voice prompt
5. `persist_events` — write Event rows with SHA256 deduplication

**Returns:** `{generated, inserted, skipped}`

---

#### KBGenerationWorkflow

| | |
|---|---|
| **Worker** | `services/worker-publishing/app/main.py` |
| **Workflow** | `services/worker-publishing/app/workflows/kb_generation.py` |
| **Task Queue** | `publishing` |
| **Purpose** | Distill claims, stats, and events into curated knowledge base entries |

**Steps (parallel where possible):**
1. `generate_player_summaries` — third-person factual summaries (10 min timeout)
2. `generate_round_briefs` — matchup/bye/injury overviews (5 min)
3. `generate_decisions_log` — historical team selection log (5 min)
4. `generate_player_opinions` — first-person opinionated takes in JeromeLu voice (10 min)
5. `generate_source_digests` — one-paragraph per-source summaries (10 min)
6. `embed_kb_entries` — generate vector embeddings for RAG retrieval (5 min)

All LLM steps use `chat_json()` (OpenAI gpt-4o, temp 0.2, JSON mode).

**Retry policy:** 3 attempts, 5s initial interval, 2x backoff.

---

#### ScraperSweepWorkflow

| | |
|---|---|
| **Worker** | `services/worker-scraper/app/main.py` |
| **Workflow** | `services/worker-scraper/app/workflows/scraper_sweep.py` |
| **Task Queue** | `scraper` |
| **Purpose** | Fetch NRL SuperCoach data (scores, prices, team lists) on a weekly schedule |

**Schedule:**
- Monday 6 AM AEST: scores
- Wednesday 6 AM AEST: prices + breakevens
- Thursday 6 PM AEST: team lists

**Input:** `ScraperSweepInput(scrape_type, round, season)`

**Steps:**
1. **Fetch** — dispatches to `fetch_scores`, `fetch_prices`, or `fetch_teamlists` based on `scrape_type`
2. **Validate** — `validate_data` (1 attempt only)
3. **Persist** — `persist_player_rounds` (only if validation passed)

**Retry policy:** Fetch: 3 attempts, 5s initial, 2x backoff; non-retryable: `AuthError`. Validate: no retry.

**Returns:** `{scrape_type, round, season, rows, validation, persist}`

**Activity implementation status:**

| Activity | File | Status | Source |
|---|---|---|---|
| `fetch_prices` | `activities/prices.py` | Implemented | `nrlsupercoachstats.com` jqGrid endpoint — 200 rows/page, extracts 70+ stat fields via `extract_all_stats()`, uploads to S3 at `prices/{season}/round_{round}.json` |
| `fetch_scores` | `activities/scores.py` | Stub (NotImplementedError) | Intended source: NRL match scores |
| `fetch_teamlists` | `activities/teamlists.py` | Stub (NotImplementedError) | Intended source: `api.nrl.com` |
| `validate_data` | `activities/validation.py` | Implemented | Row count (200-700), required fields, range checks (score 0-250, price 100k-900k, minutes 0-80), duplicate detection |
| `persist_player_rounds` | `activities/persist.py` | Implemented | Bulk upsert to `player_rounds` table via `INSERT ... ON CONFLICT DO UPDATE` — idempotent |

**Shared scraping utilities:** `packages/shared/jeromelu_shared/scraping/nrl.py` provides the `JQGRID_COLUMN_MAP` (70+ stat fields covering SC breakdown, scoring, attack, defence, discipline, price, and context columns), team name normalisation, name parsing, and `extract_all_stats()`.

---

### Standalone Fetcher Scripts

These scripts in `scripts/fetchers/` fetch NRL stats data but are **not yet wired into Temporal** — they run manually and write to local YAML files. They use the same shared scraping utilities as `worker-scraper`.

| Script | Source | Output | Purpose |
|---|---|---|---|
| `fetch_player_stats.py` | `nrlsupercoachstats.com` | `data/player_stats/round_XX.yaml` | Per-round player stats: score, price, breakeven, minutes, PPM, SC breakdown (base/attack/playmaking/power/negative), tries, assists, goals, line breaks, tackle busts, offloads, kick metres, tackles, missed tackles, intercepts, errors, penalties |
| `fetch_match_stats.py` | `nrlsupercoachstats.com` | `data/match_stats/round_XX.yaml` | Aggregated match-level summaries: groups players by team, pairs opponents, aggregates stats, lists try scorers and top SC scorers |
| `fetch_teamlists.py` | `nrlsupercoachstats.com` | `data/teamlists/round_XX.yaml` | Team lists derived from player stats: jersey 1-13 (starting), 14-17 (interchange), 18-22 (reserves) |

**Usage:** `python scripts/fetchers/fetch_player_stats.py --round 2 --season 2026`

These are candidates for promotion into `worker-scraper` Temporal activities once the stubs are replaced.

---

### Ingestion Utilities

Additional scripts and endpoints that support the ingestion pipeline but aren't Temporal workflows:

| Utility | Location | Purpose |
|---|---|---|
| `backfill.py` | `services/worker-ingestion/app/` | One-time backfill: uses `yt-dlp` to discover ALL videos from whitelisted channels, collect transcripts, upload to S3, index in DB |
| `trigger_sweep.py` | `services/worker-ingestion/app/` | Manually trigger IntelSweepWorkflow (testing/debugging) |
| `seed_channels.py` | `services/worker-ingestion/app/` | Load channels from `sources.yaml` and upsert to DB |
| `POST /admin/ingest` | `services/api/app/routers/admin.py` | Ingest transcript + claims from S3 — creates Source, SourceDocument, SourceChunks, Claims, ClaimChunks with entity resolution |
| `POST /admin/ingest-raw` | `services/api/app/routers/admin.py` | Ingest raw transcript without claims |
| `GET /admin/pipeline` | `services/api/app/routers/admin.py` | View pipeline stage for every source (discovered → collected → indexed → cleaned → extracted) |
| `GET /admin/sync-status` | `services/api/app/routers/admin.py` | Cross-reference local files, S3, and DB for mismatches |

---

### Not Yet Built

| Task Queue | Worker | Intended Purpose |
|---|---|---|
| `extraction` | `worker-extraction` | Entity, quote, and claim extraction from ingested content |
| `decision` | `worker-decision` | Scoring, ranking, and strategy generation |

Both workers exist as skeletons with empty activity/workflow lists.

---

## LLM Activity Agents

These are individual LLM-powered Temporal activities inside `worker-publishing`. Each calls OpenAI via the shared `chat_json()` helper (gpt-4o, temp 0.2, JSON mode) with a task-specific system prompt.

| Activity | File | LLM Task Type | Purpose |
|---|---|---|---|
| `generate_feed_events` | `activities/generate_events.py` | Characterisation | Convert structured claims into narrative feed events in JeromeLu's voice |
| `generate_player_summaries` | `activities/generate_kb.py` | Synthesis | Third-person factual player summaries from aggregated claims |
| `generate_player_opinions` | `activities/generate_kb.py` | Characterisation | First-person opinionated takes (bullish/bearish) in JeromeLu voice |
| `generate_round_briefs` | `activities/generate_kb.py` | Synthesis | Factual round overviews: matchups, byes, injuries, conditions |
| `generate_source_digests` | `activities/generate_kb.py` | Synthesis | One-paragraph summaries of what each source said |
| `generate_decisions_log` | `activities/generate_kb.py` | Synthesis | Historical record of JeromeLu's team selections |
| `embed_kb_entries` | `activities/generate_kb.py` | Embedding | Vector embeddings for RAG retrieval |
| `update_consensus_snapshots` | `activities/update_consensus.py` | None (deterministic) | Compute consensus scores, detect sentiment flips |
| `generate_review_data` | `activities/generate_reviews.py` | None (deterministic) | Match past predictions against actual player round scores |

LLM task types map to the categories defined in [06-llm-architecture.md](06-llm-architecture.md).

---

## Claude Code Skill Agents

### Transcript Analysis Pipeline

Documented in detail at `docs/workflow/analyse-transcript.md`.

A hierarchical multi-agent pipeline for extracting NRL SuperCoach claims from YouTube podcast transcripts. Uses progressive context building — each phase feeds the next.

| Phase | Agent | Model | Parallelism | Purpose |
|---|---|---|---|---|
| 1 | Pre-clean | Python (no LLM) | Single pass | Fix auto-caption garbles: mangled names, teams, NRL terms |
| 2 | Chapter Detection | Claude Sonnet | Single agent | Detect semantic chapter boundaries, types, team associations, sub-topic hints |
| 3 | Specialist Agents | Claude Opus | 1 per chapter (parallel) | Deep claim extraction with scoped enrichment data per chapter type |
| 4 | Verification Agents | Claude Haiku | 1 per claim (parallel) | Cross-check each claim against transcript (PASS / FLAG / FAIL) |

**Chapter types and specialist scoping:**

| Chapter Type | Enrichment Data Provided |
|---|---|
| `game_review` | Both teams' player lists + fixture data |
| `position_analysis` | All players at target positions |
| `strategy` | Full player pool + all fixtures |
| `qa_segment` | Full player pool + fixtures |
| `intro_outro` | Player name registry only |
| `tangent` | Player name registry only |

**Verification fields checked:** `claim_type`, `claim_text`, `strength`, `polarity`, `start_ts`, `end_ts`

**Related skills:**
- `/clean-transcript` — Phase 1 standalone (deterministic NLP)
- `/process-transcript` — flat single-pass extraction (1 Claude instance, simpler alternative)
- `/verify-claims` — Phase 4 standalone
- `/fetch-transcripts` — download raw transcripts from S3
- `/upload-transcript` — persist claims to DB

---

### Skill Creator Agents

Located at `.claude/skills/skill-creator/agents/`. Used by the `/skill-creator` skill for evaluating and improving Claude Code skills.

#### Blind Comparator

| | |
|---|---|
| **File** | `agents/comparator.md` |
| **Purpose** | A/B compare two skill outputs without knowing which skill produced them |
| **Method** | Generate evaluation rubric (content + structure dimensions, 1-5 scale), score both outputs, determine winner |
| **Output** | `{winner, reasoning, rubric_scores, output_quality, expectation_results}` |

#### Post-hoc Analyzer

| | |
|---|---|
| **File** | `agents/analyzer.md` |
| **Purpose** | Analyze WHY a skill output won or lost; extract improvement suggestions |
| **Input** | Comparison result + both skills + both execution transcripts |
| **Output** | `{comparison_summary, winner_strengths, loser_weaknesses, instruction_following (1-10), improvement_suggestions}` |

Also supports a **Benchmark Analyzer** mode for cross-eval pattern analysis.

#### Grader

| | |
|---|---|
| **File** | `agents/grader.md` |
| **Purpose** | Evaluate skill output against expectations; extract and verify implicit claims |
| **Input** | Expectations + execution transcript + output files |
| **Output** | `{expectations[PASS/FAIL], summary, execution_metrics, claims, eval_feedback}` |

---

## Agent Topology Summary

```
Temporal Server
├── worker-orchestrator (orchestrator queue)
│   └── (workflow definitions — intended hub, currently empty)
│
├── worker-ingestion (ingestion queue)
│   └── IntelSweepWorkflow
│       ├── discover_new_videos
│       ├── collect_transcript
│       └── index_document
│
├── worker-publishing (publishing queue)
│   ├── FeedGenerationWorkflow
│   │   ├── fetch_unprocessed_claims
│   │   ├── update_consensus_snapshots
│   │   ├── generate_review_data
│   │   ├── generate_feed_events ← LLM (characterisation)
│   │   └── persist_events
│   │
│   └── KBGenerationWorkflow
│       ├── generate_player_summaries ← LLM (synthesis)
│       ├── generate_round_briefs ← LLM (synthesis)
│       ├── generate_decisions_log ← LLM (synthesis)
│       ├── generate_player_opinions ← LLM (characterisation)
│       ├── generate_source_digests ← LLM (synthesis)
│       └── embed_kb_entries ← embedding
│
├── worker-scraper (scraper queue)
│   └── ScraperSweepWorkflow
│       ├── fetch_prices ✓
│       ├── fetch_scores ✗ (stub)
│       ├── fetch_teamlists ✗ (stub)
│       ├── validate_data ✓
│       └── persist_player_rounds ✓
│
├── worker-extraction (extraction queue) — NOT YET BUILT
└── worker-decision (decision queue) — NOT YET BUILT

Standalone Fetchers (scripts/fetchers/ — not yet in Temporal)
├── fetch_player_stats.py → data/player_stats/round_XX.yaml
├── fetch_match_stats.py  → data/match_stats/round_XX.yaml
└── fetch_teamlists.py    → data/teamlists/round_XX.yaml

Ingestion Utilities
├── backfill.py         — bulk historical import via yt-dlp
├── trigger_sweep.py    — manual workflow trigger
├── seed_channels.py    — channel config from sources.yaml
└── API /admin/*        — ingest, pipeline view, sync status

Claude Code Skills
├── Transcript Analysis Pipeline (analyse-transcript)
│   ├── Phase 1: Pre-clean (Python)
│   ├── Phase 2: Chapter Detection (Sonnet)
│   ├── Phase 3: Specialist Agents (Opus × N chapters)
│   └── Phase 4: Verification Agents (Haiku × N claims)
│
└── Skill Creator (skill-creator)
    ├── Blind Comparator
    ├── Post-hoc Analyzer
    └── Grader
```
