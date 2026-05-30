---
tags: [area/operations, data-lineage]
---

# Lineage: player_rounds

[Schema: data-catalogue/player_rounds.md](../data-catalogue/player_rounds.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| nrlsupercoachstats / stats | [data-sources/nrlsupercoachstats/stats.md](../data-sources/nrlsupercoachstats/stats.md) | **Primary** — SC scoring breakdown (base/attack/playmaking/power/negative), per-event scoring, derived metrics, averages, percentages, price tracking |
| supercoach / classic-players-cf | [data-sources/supercoach/classic-players-cf.md](../data-sources/supercoach/classic-players-cf.md) | **Lookahead overlay** (planned) — `player_stats[]` per player for forward projection |

`nrlsupercoachstats` is the **only** source for SC scoring breakdown. SC's classic-players-cf endpoint provides the lookahead overlay; SC API does not expose the breakdown.

## Writers

- `services/api/app/miner/supercoach_stats/` — primary path; reads from `miner/nrlsupercoachstats/stats/{season}/round-{NN}.json` and writes to `player_rounds`
- **Planned:** SC overlay extractor — reads `miner/supercoach/classic/players-cf/*.player_stats[]` and writes lookahead/projection columns

## Field mapping

The full ~60-column schema lives in [data-catalogue/player_rounds.md](../data-catalogue/player_rounds.md). High-level mapping:

| Column group | Source | Notes |
|---|---|---|
| Identity (`player_id`, `player_name`, `team`, `position`, `round`, `season`) | nrlsupercoachstats | `player_id` is the external SC player ID, also stored on `people.supercoach_id` for joinable identity |
| Core (`score`, `price`, `breakeven`, `minutes`, `selected_pct`) | nrlsupercoachstats | |
| SC breakdown (`base`, `attack`, `playmaking`, `power`, `negative`) | nrlsupercoachstats | **Only available from this source** |
| Per-event scoring (`tries`, `try_assists`, `goals`, etc.) | nrlsupercoachstats | |
| Attack stats (`line_breaks`, `tackle_busts`, `offloads`, `hitups_8m`, etc.) | nrlsupercoachstats | |
| Defence stats (`tackles_made`, `missed_tackles`, `intercepts`) | nrlsupercoachstats | |
| Discipline stats (`forced_dropouts`, `penalties`, `errors`, `sin_bins`, etc.) | nrlsupercoachstats | |
| Derived (`ppm`, `base_ppm`, `base_power`, `base_power_ppm`) | nrlsupercoachstats | Pre-computed by source |
| Averages (`avg_score`, `two_rd_avg`, `three_rd_avg`, `five_rd_avg`, `season_avg`) | nrlsupercoachstats | |
| Percentages (`hitup_8m_pct`, `tackle_bust_pct`, etc.) | nrlsupercoachstats | |
| Price (`start_price`, `end_price`, `round_price_change`, `season_price_change`, `magic_number`) | nrlsupercoachstats | |
| Context (`opposition`, `venue`, `weather`, `surface`, `jersey`, `bye_round`) | nrlsupercoachstats | Free-text legacy columns; pre-mig-032 |
| Canonical FKs (`match_id`, `team_id`) | resolved | New writes only (mig 032). Legacy free-text `team`/`opposition`/`venue` stay populated for historical queries |
| `created_at` | derived | DB default `now()` |

## Idempotency

Unique key: `(player_id, round, season)`. Re-runs UPSERT; columns refresh in place.

## Notes

- The legacy text columns (`team`, `opposition`, `venue`) are kept populated for historical queries that pre-date mig 032. New writes also fill `match_id` / `team_id` so future queries can JOIN to the structured world.
- nrlsupercoachstats is **only used for stats**, never for identity (its IDs are name-hashes, not stable). See [people](people.md) lineage notes.
