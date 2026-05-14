---
tags: [area/operations, data-catalogue]
---

# player_rounds

[← Data Catalogue](README.md) · Layer 2 — Structured world

Per-player SuperCoach performance overlay — one row per player per round per season. Joins to the fixture spine via `match_id` (FK→matches) and `team_id` (FK→teams). External `player_id` keys back to the SC API.

The table has ~60 columns covering core stats, SC breakdown (base / attack / playmaking / power / negative), per-event scoring, derived metrics (PPM, base+power), 2/3/5-round averages, percentage breakdowns, and price tracking. **See the [full column list](#full-column-list) at the bottom.**

Identity / FK columns (the rest are in the column list):

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| player_id | int | no | | External SC player ID |
| player_name | text | no | | |
| team | text | no | | Legacy free-text — pre-mig 032 rows |
| position | text | no | | |
| round | int | no | | |
| season | int | no | | |
| opposition | text | yes | | Legacy free-text — pre-mig 032 rows |
| venue | text | yes | | Legacy free-text — pre-mig 032 rows |
| match_id | UUID | yes | | FK → matches; new writes only (mig 032) |
| team_id | UUID | yes | | FK → teams; new writes only (mig 032) |
| created_at | timestamptz | no | now() | |
| *(scoring / derived / averages / price)* | | | | See full column list below |

**Unique:** (player_id, round, season)
**Indexes:** (season, round), player_id, match_id (partial), team_id (partial)
**FK:** match_id → matches.match_id (ON DELETE SET NULL); team_id → teams.team_id (ON DELETE SET NULL)

The legacy `team`/`opposition`/`venue` text columns stay populated so historical queries keep working; new writes (after migration 032) populate `match_id` and `team_id` alongside the text columns.

---

## Full column list

The full ~60-column shape of `player_rounds`. Unique key is `(player_id, round, season)`; FKs are `match_id → matches` and `team_id → teams` (both nullable, populated for new writes after migration 032).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| player_id | int | no | | External player ID |
| player_name | text | no | | |
| team | text | no | | |
| position | text | no | | |
| round | int | no | | |
| season | int | no | | |
| **Core** | | | | |
| score | int | yes | | SC total score |
| price | int | yes | | Current price |
| breakeven | int | yes | | BE score |
| minutes | int | yes | | Minutes played |
| selected_pct | float | yes | | Ownership % |
| **SC Breakdown** | | | | |
| base | int | yes | | Base SC points |
| attack | int | yes | | Attack SC points |
| playmaking | int | yes | | Playmaking SC points |
| power | int | yes | | Power SC points |
| negative | int | yes | | Negative SC points |
| **Scoring** | | | | |
| tries | int | yes | | |
| try_assists | int | yes | | |
| goals | int | yes | | |
| missed_goals | int | yes | | |
| field_goals | int | yes | | |
| missed_field_goals | int | yes | | |
| **Attack** | | | | |
| line_breaks | int | yes | | |
| line_break_assists | int | yes | | |
| last_touch | int | yes | | |
| tackle_busts | int | yes | | |
| offloads | int | yes | | |
| ineffective_offloads | int | yes | | |
| hitups_8m | int | yes | | Hitups gaining 8+ metres |
| hitups_under_8m | int | yes | | Hitups gaining <8 metres |
| kick_metres | int | yes | | |
| **Defence** | | | | |
| tackles_made | int | yes | | |
| missed_tackles | int | yes | | |
| intercepts | int | yes | | |
| **Discipline** | | | | |
| forced_dropouts | int | yes | | |
| forty_twentys | int | yes | | |
| kicked_dead | int | yes | | |
| penalties | int | yes | | |
| errors | int | yes | | |
| sin_bins | int | yes | | |
| handover_given | int | yes | | |
| **Derived** | | | | |
| ppm | float | yes | | Points per minute |
| base_ppm | float | yes | | Base points per minute |
| base_power | int | yes | | base + power |
| base_power_ppm | float | yes | | (base + power) / minutes |
| **Averages** | | | | |
| avg_score | float | yes | | Season average |
| two_rd_avg | float | yes | | Last 2 rounds |
| three_rd_avg | float | yes | | Last 3 rounds |
| five_rd_avg | float | yes | | Last 5 rounds |
| season_avg | float | yes | | Full season average |
| **Percentages** | | | | |
| hitup_8m_pct | float | yes | | hitups_8m / total hitups |
| tackle_bust_pct | float | yes | | |
| missed_tackle_pct | float | yes | | |
| offload_involvement_pct | float | yes | | |
| base_pct | float | yes | | base / score |
| **Price** | | | | |
| start_price | int | yes | | Price at round start |
| end_price | int | yes | | Price at round end |
| round_price_change | int | yes | | |
| season_price_change | int | yes | | |
| magic_number | int | yes | | Score needed to increase in price |
| **Context** | | | | |
| opposition | text | yes | | Legacy free-text — pre-mig 032 rows |
| venue | text | yes | | Legacy free-text — pre-mig 032 rows |
| weather | text | yes | | |
| surface | text | yes | | |
| jersey | int | yes | | Jersey number |
| bye_round | text | yes | | |
| **Canonical FKs (mig 032)** | | | | |
| match_id | UUID | yes | | FK → matches; new writes only |
| team_id | UUID | yes | | FK → teams; new writes only |
| created_at | timestamptz | no | now() | |
