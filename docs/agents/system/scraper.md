---
tags: [area/agents, subarea/system, status/partial]
---

# Scraper

> **Reframe note (2026-05-12).** Per the [Scout charter expansion](../../architecture/drafts/scout-charter-expansion.draft.md), the scraper is a **Scout component, marked for retirement**. The Temporal-shaped `worker-scraper` is being unwound: its activities migrate into `services/api/app/scout/data/` as plain functions wrapped by admin endpoints, all writing under `agent_id='scout'` with a `detail_json.pipeline` discriminator. The "Fixture / Match / Injury sync (planned)" section below describes pipelines that are now part of Scout's expanded charter and will be built there, not as new Temporal activities. The Bookkeeper consumes the resulting `player_rounds` rows but no longer owns the acquisition.
>
> This doc remains as the historical reference for the Temporal worker until it's retired in Phase 4 of the charter rollout. New scraping work should look at [`scout.md`](../crew/scout.md) and the [charter expansion draft](../../architecture/drafts/scout-charter-expansion.draft.md), not here.

| | |
|---|---|
| **Worker** | `services/worker-scraper/app/main.py` *(legacy; marked for retirement)* |
| **Task Queue** | `scraper` |
| **New crew counterpart** | [Scout](../crew/scout.md) *(Bookkeeper consumes downstream)* |
| **Status** | Active in dev only; per-project-memory, Temporal is not in production. |

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

---

## Fixture / Match / Injury sync — now Scout modules

The schema-side groundwork landed in migrations 028–032 — `venues`,
`matches`, `match_team_lists`, `injuries`, plus `match_id` / `team_id`
FKs on `player_rounds`. See [data-catalogue](../../operations/data-catalogue.md)
for table shapes.

Five sync jobs build on top. **These are now formalised as Scout modules
under the [charter expansion](../../architecture/drafts/scout-charter-expansion.draft.md)**
— sibling to media discovery, sharing one `agent_id='scout'` audit
identity with `detail_json.pipeline` discriminating. They're cron-driven
admin endpoints, not Temporal activities.

| Job | Scout module | Cadence | Source | Writes to |
|---|---|---|---|---|
| `sync_fixtures` | `scout/data/nrlcom_matches.py` | Daily 5am AEST | NRL.com draw API | `matches` (upsert on source + external id) |
| `sync_team_lists` | `scout/data/nrlcom_teamlists.py` | Tue 1pm, Wed 6pm, Thu 6pm AEST | NRL.com match centre | `match_team_lists` (new `list_version` per pull) |
| `sync_match_results` | `scout/data/nrlcom_matches.py` (shared module) | Hourly Fri evening → Mon noon AEST | NRL.com match centre | `matches.status/score`, late-change `match_team_lists` |
| `sync_injuries` | `scout/data/nrlcom_injuries.py` | Daily 8am + Tue 5pm AEST | NRL.com casualty ward (primary), Zero Tackle (cross-ref) | `injuries` (append-on-change) |
| `sync_supercoach` | `scout/data/supercoach_stats.py` | Mon / Wed / Thu | SuperCoach API | `player_rounds` (now also stamps `match_id`, `team_id`) |

All five run under `agent_id='scout'` per D6 of the charter expansion;
the `pipeline` field in `agent_runs.detail_json` is what distinguishes
them in dashboards. NRL.com is the canonical spine for the fixture and
team-list data; SuperCoach API is the fantasy-stats overlay; NRL Physio
Twitter remains in the claim-extraction pipeline rather than being
parsed structurally.
