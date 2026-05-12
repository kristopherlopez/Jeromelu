# Scout / SuperCoach Settings

Snapshots SuperCoach's game-rules configuration per season.

| Field | Value |
|---|---|
| Source of truth | `supercoach.com.au/{season}/api/nrl/classic/v1/settings` |
| Cadence | Weekly (rarely changes mid-season) |
| Natural key | `(season, captured_date, mode)` on `sc_settings` |
| Owner | Scout |
| Pipeline label | `supercoach-settings` |
| Endpoint | `POST /api/admin/scout/supercoach-settings` |
| Make target | `make scout-supercoach-settings ADMIN_KEY=$ADMIN_KEY` |
| S3 archive | `scout/supercoach/classic/settings/{season}/{YYYYMMDD}.json` |
| DB table | `sc_settings` (migration 055) |

## What gets captured

The response is ~15KB of nested JSON. Top-level keys:

- `competition` — current round, lockout state/window, num_users, status
- `content` — UI display strings (athlete plural, currency symbol, gameLength, hashtag, etc.)
- `game` — 69 sub-keys: captains, emergencies, dnp, dual_position_players, scoring config, eliminator, club_championship, experts, final_scoring_round
- `system` — currency, data_version, timezone

Stored whole as JSONB in `sc_settings.payload`. The strict Pydantic model
validates only the four top-level keys exist — deep field churn under those
keys is treated as opaque (this is rules data, evolves slowly).

## Idempotency

Per D7: unique on `(season, captured_date, mode)`. Same-day re-runs are a no-op
upsert. New day → new row → preserves daily history.
