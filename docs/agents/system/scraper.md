---
tags: [area/agents, subarea/system, status/retired]
---

# Scraper

> **🪦 Retired and deleted 2026-05-28** (Miner Phase 4 closure, TASK-28). The `services/worker-scraper/` Temporal worker has been removed from the repository — its activities never ran in production, and every pipeline it owned (or was a stub for) now lives under `services/api/app/miner/<pipeline>/` per the [Miner charter expansion](../crew/miner/charter.md) (D4). New scraping work goes there, wrapped by admin endpoints under `agent_id='miner'`. This doc remains as the **historical reference** for what the worker did before retirement; the corresponding crew counterpart is [Miner](../crew/miner/README.md).

| | |
|---|---|
| **Worker** | ~~`services/worker-scraper/app/main.py`~~ *(retired and deleted 2026-05-28)* |
| **Task Queue** | `scraper` (no longer registered) |
| **Replacement** | [Miner](../crew/miner/README.md) — per-pipeline folders under `services/api/app/miner/`, admin-endpoint-driven, audited under `agent_id='miner'` |
| **Status** | **Retired.** Never reached production; Temporal is not deployed (per project memory). |

---

## ScraperSweepWorkflow

| | |
|---|---|
| **Workflow** | ~~`services/worker-scraper/app/workflows/scraper_sweep.py`~~ *(deleted 2026-05-28)* |
| **Purpose** | Fetch NRL SuperCoach data (scores, prices, team lists) on a weekly schedule — superseded by `services/api/app/miner/supercoach_stats/` (shipped Phase 2) and the nrl.com Miner pipelines (Phases 3–4) |

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

In `scripts/fetchers/`. Fetch NRL stats but were **never wired into Temporal** — they run manually and write to local YAML files. They use the same shared scraping utilities the (now-retired) `worker-scraper` did.

| Script | Source | Output | Purpose |
|---|---|---|---|
| `fetch_player_stats.py` | `nrlsupercoachstats.com` | `data/player_stats/round_XX.yaml` | Per-round player stats: score, price, breakeven, minutes, PPM, SC breakdown (base/attack/playmaking/power/negative), tries, assists, goals, line breaks, tackle busts, offloads, kick metres, tackles, missed tackles, intercepts, errors, penalties |
| `fetch_match_stats.py` | `nrlsupercoachstats.com` | `data/match_stats/round_XX.yaml` | Aggregated match-level summaries: groups players by team, pairs opponents, aggregates stats, lists try scorers and top SC scorers |
| `fetch_teamlists.py` | `nrlsupercoachstats.com` | `data/teamlists/round_XX.yaml` | Team lists derived from player stats: jersey 1-13 (starting), 14-17 (interchange), 18-22 (reserves) |

**Usage:** `python scripts/fetchers/fetch_player_stats.py --round 2 --season 2026`

These were historically candidates for promotion into `worker-scraper` Temporal activities. With `worker-scraper` retired, future structural work on them follows the Miner pattern instead — per-pipeline folders under `services/api/app/miner/`, admin-endpoint-driven.

---

## Fixture / Match / Injury sync — now Miner modules

The schema-side groundwork landed in migrations 028–032 — `venues`,
`matches`, `match_team_lists`, `injuries`, plus `match_id` / `team_id`
FKs on `player_rounds`. See [data-catalogue](../../operations/data-catalogue/README.md)
for table shapes.

Five sync jobs build on top. **These are now formalised as Miner modules
under the [charter expansion](../crew/miner/charter.md)**
— sibling to media discovery, sharing one `agent_id='miner'` audit
identity with `detail_json.pipeline` discriminating. They're cron-driven
admin endpoints, not Temporal activities.

| Job | Miner module folder | Cadence | Source | Writes to |
|---|---|---|---|---|
| `sync_fixtures` | `services/api/app/miner/nrlcom_matches/` | Daily 5am AEST | NRL.com draw API | `matches` (upsert on source + external id) |
| `sync_team_lists` | `services/api/app/miner/nrlcom_teamlists/` | Tue 1pm, Wed 6pm, Thu 6pm AEST | NRL.com match centre | `match_team_lists` (new `list_version` per pull) |
| `sync_match_results` | `services/api/app/miner/nrlcom_matches/` (shared with fixtures) | Hourly Fri evening → Mon noon AEST | NRL.com match centre | `matches.status/score`, late-change `match_team_lists` |
| `sync_injuries` | `services/api/app/miner/nrlcom_injuries/` | Daily 8am + Tue 5pm AEST | NRL.com casualty ward (primary), Zero Tackle (cross-ref) | `injuries` (append-on-change) |
| `sync_supercoach` | `services/api/app/miner/supercoach_stats/` | Mon / Wed / Thu | SuperCoach API | `player_rounds` (now also stamps `match_id`, `team_id`) |

All five run under `agent_id='miner'` per D6 of the charter expansion;
the `pipeline` field in `agent_runs.detail_json` is what distinguishes
them in dashboards. NRL.com is the canonical spine for the fixture and
team-list data; SuperCoach API is the fantasy-stats overlay; NRL Physio
Twitter remains in the claim-extraction pipeline rather than being
parsed structurally.
