# Miner / SuperCoach Stats

Fetches per-round (or Totals) SuperCoach stats from
`nrlsupercoachstats.com` and upserts into `player_rounds`.

| Field | Value |
|---|---|
| Source of truth | `nrlsupercoachstats.com` jqGrid endpoint (unauthenticated, third party) |
| Cadence | Cron via `scripts/miner-refresh.sh supercoach-stats current` at Sun/Tue/Thu 22:55 UTC (Mon/Wed/Fri 08:55 AEST). The wrapper resolves the current round from SuperCoach settings; ad-hoc runs pass an explicit `ROUND`. |
| Natural key | `(player_id, season, round)` on `player_rounds` |
| Owner | Miner |
| Pipeline label | `supercoach-stats` (kebab; in `agent_runs.detail_json.pipeline` and the admin URL) |
| Audit | `agent_id='miner'` per D6 of the charter |
| Endpoint | `POST /api/admin/miner/supercoach-stats?round=N&season=Y` |
| Make target | `make miner-supercoach-stats ADMIN_KEY=$ADMIN_KEY ROUND=N [SEASON=2026]` |
| Drift contract | D8 — strict Pydantic on the **extracted** shape (`SuperCoachPlayerStats`, ~58 fields). Catches renames/removals of fields we depend on. Fixture: `tests/fixtures/miner/supercoach_stats/canonical_response.json`. |

## What `round` means

- `round=0` → "Totals" (cumulative season-to-date or pre-season aggregate from the previous season). Useful pre-season and as a baseline.
- `round>0` → per-round stats for that specific round of the current season.

## What gets written

Each row in `player_rounds` carries 4 identity columns + 4 base columns + ~49 stat columns derived from `JQGRID_COLUMN_MAP` in `jeromelu_shared.scraping.nrl`.

| Column group | Examples |
|---|---|
| Identity | `player_id`, `player_name`, `team`, `position`, `round`, `season` |
| Base | `score`, `price`, `breakeven`, `minutes` |
| SC breakdown | `base`, `attack`, `playmaking`, `power`, `negative` |
| Scoring | `tries`, `try_assists`, `goals`, `field_goals`, … |
| Attack | `line_breaks`, `tackle_busts`, `offloads`, `hitups_8m`, … |
| Defence | `tackles_made`, `missed_tackles`, `intercepts` |
| Discipline | `forced_dropouts`, `penalties`, `errors`, `sin_bins`, … |
| Derived | `ppm`, `base_ppm`, `base_power`, `base_power_ppm` |
| Averages | `avg_score`, `two_rd_avg`, `three_rd_avg`, `season_avg` |
| Percentages | `base_pct`, `hitup_8m_pct`, `tackle_bust_pct`, … |
| Price | `start_price`, `end_price`, `round_price_change`, `season_price_change`, `magic_number` |
| Context | `opposition`, `venue`, `weather`, `surface`, `jersey`, `bye_round` |

## Idempotency

Per D7 of the charter, upserts conflict on `(player_id, round, season)` via the `uq_player_round_season` constraint. Re-running the same round/season is a no-op apart from refreshing time-varying fields (price changes, ownership, etc.).

## Drift detection

The strict Pydantic model is over the **extracted** shape, not the raw jqGrid row (which has ~95 fields including many we don't extract). If the upstream renames or removes a field in `JQGRID_COLUMN_MAP`, `extract_all_stats` returns `None` for it, and the strict model fails on the missing required value. The test catches both — fixture-mode against the checked-in canonical response, live-mode (env-flagged) against the real endpoint.

## Legacy code

The Temporal-shaped equivalent used to live in `services/worker-scraper/app/activities/{prices,persist,validation}.py`. That worker was **retired and deleted 2026-05-28** (Miner Phase 4 closure / TASK-28). The shared utilities in `jeromelu_shared.scraping.nrl` remain canonical.
