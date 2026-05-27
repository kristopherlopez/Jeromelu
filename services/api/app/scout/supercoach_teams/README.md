# Scout / SuperCoach Teams

Cross-references SuperCoach's internal team IDs into our `teams` table.

| Field | Value |
|---|---|
| Source of truth | `supercoach.com.au/{season}/api/nrl/classic/v1/teams` |
| Cadence | Weekly (rarely changes) |
| Natural key | `teams.short_name` lookup by SC `abbrev` → SC ID written to `teams.metadata_json.supercoach` |
| Owner | Scout |
| Pipeline label | `supercoach-teams` |
| Audit | `agent_id='scout'`, `detail_json.pipeline='supercoach-teams'` |
| Endpoint | `POST /api/admin/scout/supercoach-teams` |
| Make target | `make scout-supercoach-teams ADMIN_KEY=$ADMIN_KEY` |
| S3 archive | `scout/supercoach/classic/teams/{season}.json` |

## What gets written

Each SC team row in the response carries `id`, `abbrev`, `feed_name`, `name`, `competition`. We:

1. Match `abbrev` (e.g. `BRO`) against `SC_ABBREV_TO_TEAM_SLUG` (the canonical mapping in `jeromelu_shared.players.roster`) to find our `teams` row.
2. Write `teams.metadata_json.supercoach = {id, abbrev, feed_name, name, competition}` so downstream code can join SC's team IDs to ours.

## Idempotency

Per D7: re-running rewrites the same JSONB block. No new rows; no schema change.

## Tests

- `tests/unit/api/scout/supercoach_teams/test_models.py` — always-on D8 drift unit tests against the checked-in canonical fixture (`tests/fixtures/scout/supercoach_teams/canonical_response.json`): canonical parse (17 teams, NRL competition) plus strict `extra="forbid"` negatives on the team envelope and the nested competition object.
- `tests/integration/scout/supercoach_teams/test_response_shape.py` — env-flagged live drift test (`SCOUT_DRIFT_LIVE=1`); hits the real `/teams` endpoint and strict-parses every team. Skipped in CI by default. Per D8 the agent does not auto-adapt — a live shape change fails the test and routes to the operator.
