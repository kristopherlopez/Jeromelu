# Scraper

| | |
|---|---|
| **Worker** | `services/worker-scraper/app/main.py` |
| **Task Queue** | `scraper` |
| **Crew counterpart** | [Bookkeeper](../crew/bookkeeper.md) |

---

## ScraperSweepWorkflow

| | |
|---|---|
| **Workflow** | `services/worker-scraper/app/workflows/scraper_sweep.py` |
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

**Retry policy:** Fetch: 3 attempts, 5s initial, 2× backoff; non-retryable: `AuthError`. Validate: no retry.

**Returns:** `{scrape_type, round, season, rows, validation, persist}`

### Activity Implementation Status

| Activity | File | Status | Source |
|---|---|---|---|
| `fetch_prices` | `activities/prices.py` | Implemented | `nrlsupercoachstats.com` jqGrid endpoint — 200 rows/page, extracts 70+ stat fields via `extract_all_stats()`, uploads to S3 at `prices/{season}/round_{round}.json` |
| `fetch_scores` | `activities/scores.py` | Stub (NotImplementedError) | Intended source: NRL match scores |
| `fetch_teamlists` | `activities/teamlists.py` | Stub (NotImplementedError) | Intended source: `api.nrl.com` |
| `validate_data` | `activities/validation.py` | Implemented | Row count (200-700), required fields, range checks (score 0-250, price 100k-900k, minutes 0-80), duplicate detection |
| `persist_player_rounds` | `activities/persist.py` | Implemented | Bulk upsert to `player_rounds` table via `INSERT ... ON CONFLICT DO UPDATE` — idempotent |

**Shared scraping utilities:** `packages/shared/jeromelu_shared/scraping/nrl.py` provides the `JQGRID_COLUMN_MAP` (70+ stat fields covering SC breakdown, scoring, attack, defence, discipline, price, and context columns), team name normalisation, name parsing, and `extract_all_stats()`.

---

## Standalone Fetcher Scripts

In `scripts/fetchers/`. Fetch NRL stats but are **not yet wired into Temporal** — they run manually and write to local YAML files. They use the same shared scraping utilities as `worker-scraper`.

| Script | Source | Output | Purpose |
|---|---|---|---|
| `fetch_player_stats.py` | `nrlsupercoachstats.com` | `data/player_stats/round_XX.yaml` | Per-round player stats: score, price, breakeven, minutes, PPM, SC breakdown (base/attack/playmaking/power/negative), tries, assists, goals, line breaks, tackle busts, offloads, kick metres, tackles, missed tackles, intercepts, errors, penalties |
| `fetch_match_stats.py` | `nrlsupercoachstats.com` | `data/match_stats/round_XX.yaml` | Aggregated match-level summaries: groups players by team, pairs opponents, aggregates stats, lists try scorers and top SC scorers |
| `fetch_teamlists.py` | `nrlsupercoachstats.com` | `data/teamlists/round_XX.yaml` | Team lists derived from player stats: jersey 1-13 (starting), 14-17 (interchange), 18-22 (reserves) |

**Usage:** `python scripts/fetchers/fetch_player_stats.py --round 2 --season 2026`

These are candidates for promotion into `worker-scraper` Temporal activities once the stubs are replaced.
