# Scout / SuperCoach Roster

Acquires the NRL player roster from SuperCoach and applies the SCD-2
refresh to `people` / `people_attributes` / `people_roles`.

| Field | Value |
|---|---|
| Source of truth | `supercoach.com.au` `players-cf` endpoint (unauthenticated GET) |
| Cadence | Daily |
| Natural key | `external_id` on `people` (the SuperCoach `id` field) |
| Owner | Scout |
| Pipeline label | `supercoach-roster` (kebab; appears in `agent_runs.detail_json.pipeline` and the admin URL) |
| Audit | `agent_id='scout'` per D6 of the charter |
| Endpoint | `POST /api/admin/scout/supercoach-roster` |
| Make target | `make scout-supercoach-roster ADMIN_KEY=$ADMIN_KEY` |
| Drift contract | D8 — strict Pydantic on the structural envelope (`SuperCoachPlayer`, `SCTeam`, `SCPosition`, `SCPlayedStatus`); opaque on `player_stats`/`odds`/`notes` (those are Phase 2's concern via `supercoach_stats`). Fixture: `tests/fixtures/scout/supercoach_roster/canonical_response.json`. |

## Files

- `__init__.py` — exports the FastAPI router.
- `fetcher.py` — thin wrapper around `jeromelu_shared.players.supercoach.fetch_supercoach_roster` that adds strict Pydantic parsing.
- `models.py` — Pydantic strict models (`Config.extra='forbid'`) for the response envelope.
- `routes.py` — `POST /api/admin/scout/supercoach-roster` with the agent_audit wrapper.

## What gets written

| Table | What | Source field |
|---|---|---|
| `people` | One row per SC player | `id` (external_id) + `first_name` + `last_name` |
| `people_attributes` | Current attributes (team, primary position, contract) | `team.abbrev` (→ team_id via slug lookup), `positions[0].position` |
| `people_roles` | Primary role row (`player`) | derived |

Refresh logic — including SCD-2 close-current-open-new transitions on team / primary position changes — lives in `jeromelu_shared.players.roster.refresh_roster`. This pipeline just orchestrates the call.

## Idempotency

Per D7 of the charter, the upsert natural key is `external_id` on `people`. Re-running the same fetch with no upstream change is a no-op (SCD-2 only fires when team or primary position differs from the current row).

## Legacy back-compat

`POST /api/admin/players/fetch-and-refresh` is the deprecated alias. It calls the same handler. New callers should use `/api/admin/scout/supercoach-roster`.
