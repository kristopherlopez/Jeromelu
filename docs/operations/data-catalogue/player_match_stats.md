---
tags: [area/operations, data-catalogue]
---

# player_match_stats

[← Data Catalogue](README.md) · [Lineage](../data-lineage/player_match_stats.md) · Layer 2 — Structured world

Per-player per-match ~58-field stat line from nrl.com match-centre. One row per (match, player). `nrlcom_player_id` is the canonical identity (statsperform IDs); `person_id` is a nullable FK populated by the extractor when name resolution succeeds against [people](people.md). Added in mig 056.

Identity / FK / context columns:

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| match_id | UUID | yes | | FK → matches (CASCADE) |
| nrlcom_match_id | text | no | | nrl.com matchId |
| nrlcom_player_id | bigint | no | | statsperform player id |
| person_id | UUID | yes | | FK → people; resolved by extractor |
| team_id | UUID | yes | | FK → teams |
| nrlcom_team_id | bigint | yes | | |
| is_home | bool | no | | |
| jersey_number | int | yes | | From the team roster, joined back by playerId |
| position | text | yes | | Same |
| is_on_field | bool | yes | | Same |
| raw_payload | jsonb | no | | Full per-player block (forensic capture) |
| s3_archive_key | text | yes | | |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | |

Stat columns (~58, modelled per nrl.com camelCase fields, mapped to snake_case in `phase_stats.py:_FIELD_MAP`):

- **Time:** minutes_played, stint_one
- **Scoring:** points, tries, try_assists, conversions, conversion_attempts, goal_conversion_rate, goals, penalty_goals, field_goals, one_point_field_goals, two_point_field_goals, fantasy_points_total
- **Run/attack:** all_runs, all_run_metres, post_contact_metres, hit_ups, hit_up_run_metres, dummy_half_runs, dummy_half_run_metres, dummy_passes, passes, passes_to_run_ratio, receipts, line_breaks, line_break_assists, tackle_breaks, line_engaged_runs
- **Kicking:** kicks, kick_metres, kick_return_metres, kicks_defused, kicks_dead, bomb_kicks, grubber_kicks, cross_field_kicks, forced_drop_out_kicks, forty_twenty_kicks, twenty_forty_kicks
- **Defence:** tackles_made, missed_tackles, ineffective_tackles, tackle_efficiency, intercepts, offloads, one_on_one_steal, one_on_one_lost, play_the_ball_total, play_the_ball_average_speed
- **Discipline:** handling_errors, errors, penalties, ruck_infringements, offside_within_ten_metres, sin_bins, send_offs, on_report

**Unique:** `(nrlcom_match_id, nrlcom_player_id)` — one stat-line per (match, player). Re-runs UPSERT
**Indexes:** match_id, person_id, team_id
**FK:** match_id → matches (CASCADE); person_id → people; team_id → teams

Modelled as an explicit column per upstream field to satisfy D8 — drift on any column raises in the strict Pydantic extractor. `raw_payload` keeps the whole upstream block so future-discovered columns can be derived without re-fetching.
