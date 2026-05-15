---
tags: [area/operations, data-catalogue]
---

# match_timeline

[← Data Catalogue](README.md) · [Lineage](../data-lineage/match_timeline.md) · Layer 2 — Structured world

Typed play-by-play events per match from nrl.com match-centre. ~100-120 events per match — KICK OFF, Try, Goal, Penalty, KickBomb, LineBreak, Error, SetRestart, RuckInfringement, OffsideWithinTenMetres, LineDropout, CaptainsChallenge, SinBin, SendOff, etc. Each carries `gameSeconds + teamId + title`. Added in mig 057; `running_*_score` columns added in mig 064.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| match_id | UUID | yes | | FK → matches (CASCADE) |
| nrlcom_match_id | text | no | | nrl.com matchId |
| sequence | int | no | | 0..N per match, preserves order |
| event_type | text | no | | `Try`, `Goal`, `SetRestart`, `GameTime`, `KickBomb`, ... |
| title | text | yes | | `KICK OFF`, `TRY!` etc. |
| game_seconds | int | yes | | Seconds since match start (0..4800 for full 80-min game) |
| nrlcom_team_id | bigint | yes | | Which team initiated the event (0 for neutral game-state events) |
| team_id | UUID | yes | | FK → teams; resolved from `nrlcom_team_id` |
| nrlcom_player_id | bigint | yes | | Captured for events that reference a player (Try, Goal, etc.) |
| person_id | UUID | yes | | FK → people; resolved from `nrlcom_player_id` |
| running_home_score | int | yes | | Score at the time of this event (mig 064) |
| running_away_score | int | yes | | Same |
| raw_payload | jsonb | no | | Full event payload |
| s3_archive_key | text | yes | | |
| created_at | timestamptz | no | now() | |

**Unique:** `(nrlcom_match_id, sequence)` — UPSERT idempotent
**Indexes:** match_id, event_type, person_id (partial: WHERE NOT NULL)
**FK:** match_id → matches (CASCADE); team_id → teams; person_id → people
