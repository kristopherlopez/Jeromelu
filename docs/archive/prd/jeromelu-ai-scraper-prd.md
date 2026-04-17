---
project: JeromeLu.ai — Supercoach Data Scraper
parent: [[projects/active/jeromelu-ai]]
status: active
created: 2026-03-12
---

# PRD: Supercoach Data Scraper

## Problem

JeromeLu.ai's decision engine needs weekly Supercoach and NRL data (scores, prices, breakevens, team lists) to make informed SuperCoach moves. No official API exists. Data must be scraped, stored, and made available to the decision engine reliably across the season.

## Goal

An additional ingestion pipeline — alongside the existing content/transcript pipeline — that collects Supercoach player data after each round and stores it in S3 and Postgres, available to the decision engine and consensus snapshots.

## Non-Goals

- Real-time or live-match data collection
- Fantasy platforms other than NRL Supercoach
- Building a public data API
- Replacing the existing content ingestion pipeline (this is additive)

## Data to Collect

### Core (MVP)

| Data Point | Source | Frequency | Timing |
|-----------|--------|-----------|--------|
| Player scores | Supercoach API | Weekly | Monday (after round completes) |
| Player prices | Supercoach API | Weekly | Tuesday/Wednesday (when prices update) |
| Player breakevens | Supercoach API or derived | Weekly | After price update |
| Player metadata | Supercoach API | Weekly | Season start + weekly for position/team changes |
| Team lists | NRL API (`api.nrl.com`) | Weekly | Thursday (when teams announced) |

### Enhanced (Phase 2)

| Data Point | Source | Frequency |
|-----------|--------|-----------|
| Detailed match stats (tackles, runs, possessions, minutes) | NRL API | Weekly post-round |
| Injury lists | NRL API / news | Weekly |
| Fixture schedule + bye rounds | NRL API | Season start |

## Architecture

This pipeline uses the same infrastructure already in place for the content ingestion pipeline: Temporal for orchestration, S3/MinIO for storage, and the shared package for DB/S3/config utilities.

```
Temporal Schedules
    │
    ├── Monday 6AM AEST:   ScraperSweepWorkflow (type=scores)
    │                         ├── fetch_scores (Activity)       → S3 + DB
    │                         └── validate_data (Activity)      → fail loudly on quality issues
    │
    ├── Wednesday 6AM AEST: ScraperSweepWorkflow (type=prices)
    │                         ├── fetch_prices (Activity)       → S3 + DB
    │                         └── validate_data (Activity)
    │
    └── Thursday 6PM AEST:  ScraperSweepWorkflow (type=teamlists)
                              ├── fetch_teamlists (Activity)    → S3 + DB
                              └── validate_data (Activity)
```

### Leveraging Existing Infrastructure

| Component | Already Built | Used By This Pipeline |
|-----------|--------------|----------------------|
| Temporal orchestration | Yes (ingestion worker) | Workflows, schedules, retries |
| S3/MinIO | Yes (jeromelu-raw-transcripts bucket) | New bucket: `jeromelu-player-data` |
| PostgreSQL + pgvector | Yes (sources, source_documents, etc.) | New tables for player round data |
| Shared package | Yes (config, db, s3, temporal utilities) | Config, S3 uploads, DB sessions |
| Docker Compose | Yes (Postgres, MinIO, Temporal, Temporal UI) | No changes needed |

### Storage

- **S3 bucket:** `jeromelu-player-data`
- **Format:** Parquet (typed, compressed, columnar)
- **Key pattern:** `{data_type}/{season}/round_{n}.parquet` (e.g. `scores/2026/round_05.parquet`)
- **Combined dataset:** `combined/{season}.parquet` (updated after each scrape)

### New Database Table — `player_rounds`

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| player_id | int | Supercoach unique ID |
| player_name | str | Full name |
| team | str | NRL team code |
| position | str | Supercoach position (FRF, 2RF, HFB, etc.) |
| round | int | Round number |
| season | int | Season year |
| score | int | Supercoach points scored |
| price | int | Player price (dollars) |
| breakeven | int | Score needed to maintain price |
| minutes | int | Minutes played (if available) |
| selected_pct | float | % of Supercoach teams that own this player |
| created_at | timestamptz | When record was ingested |

Unique constraint on `(player_id, round, season)`.

### Service Placement

This pipeline should live in a new worker service: `services/worker-scraper/`. It follows the same structure as `worker-ingestion`:

```
services/worker-scraper/
├── app/
│   ├── main.py              # Temporal worker entrypoint
│   ├── workflows/
│   │   └── scraper_sweep.py  # ScraperSweepWorkflow
│   └── activities/
│       ├── scores.py          # fetch_scores
│       ├── prices.py          # fetch_prices
│       ├── teamlists.py       # fetch_teamlists
│       └── validation.py      # validate_data
├── requirements.txt
└── Dockerfile
```

Temporal queue: `SCRAPER_QUEUE` (add to `packages/shared/jeromelu_shared/temporal.py`).

## Data Quality

Each scrape activity validates before writing:
- **Schema check** — all expected columns present, correct types
- **Row count** — expected number of players (flag if <400 or >600)
- **Null check** — no nulls in player_id, score, price
- **Range check** — scores 0-200, prices 100k-900k, minutes 0-80
- **Duplicate check** — no duplicate player_id per round

Failed validation → Temporal activity failure → retry with backoff → alert after exhausted retries.

## Backfill

Bootstrap with 2024 + 2025 historical data from community sources (SupercoachTalk CSVs, GitHub repos). Clean and conform to the same schema. Backfill script follows the same pattern as `worker-ingestion/app/backfill.py`.

## Technical Notes

- **Auth:** Supercoach API requires a logged-in session. Store session cookie/token in AWS Secrets Manager (production) or `.env` (local dev). Refresh mechanism needed if tokens expire.
- **Rate limiting:** Be respectful. Single sequential requests with 1-2s delays. All scraping happens in a narrow window post-round.
- **Resilience:** Temporal retry policy — 3 attempts, 5s initial interval, 2x backoff. Non-retryable on auth failures (need manual token refresh).
- **Libraries:** `httpx` (HTTP), `polars` (data/parquet), `boto3` via shared package (S3).

## Success Criteria

1. After each NRL round, scores + prices + team lists are in S3 and Postgres within 24h of availability — no manual intervention
2. All data passes validation checks before write
3. Decision engine can query `player_rounds` table for current and historical player data

## Milestones

| # | Milestone | Target |
|---|-----------|--------|
| 1 | Backfill 2024-2025 data, confirm schema + migration | Week 1 |
| 2 | MVP scraper: scores + prices via Temporal workflow, manual trigger | Week 1-2 |
| 3 | Validation activity + S3 parquet storage | Week 2 |
| 4 | Temporal schedule automation (Monday/Wednesday/Thursday) | Week 2-3 |
| 5 | Enhanced stats from NRL API | Phase 2 |
