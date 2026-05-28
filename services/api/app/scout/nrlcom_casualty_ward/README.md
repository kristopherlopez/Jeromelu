# Scout / nrl.com Casualty Ward

Daily snapshot of the official league-wide injury roll.

| Field | Value |
|---|---|
| Source | `nrl.com/casualty-ward/data?competition=N` |
| Cadence | Daily cron — 18:30 UTC (04:30 AEST) for NRL (comp 111); see `scripts/cron.d/jeromelu` |
| Historical reach | Current season only — no historical query param |
| Pipeline label | `nrlcom-casualty-ward` |
| Endpoint | `POST /api/admin/scout/nrlcom-casualty-ward[?season=Y][&competition=N]` |
| Make target | `make scout-nrlcom-casualty-ward [SEASON=2026] [COMPETITION=111]` |
| S3 archive | `scout/nrlcom/casualty-ward/{comp}/{YYYYMMDD}.json` (timestamped — preserves daily history) |
| DB extraction | `scripts/data/populate/phase_aux.py:populate_injuries` — state machine over chronologically-sorted snapshots → `injuries` (lineage: [data-lineage/injuries.md](../../../../../docs/operations/data-lineage/injuries.md)) |

Each casualty entry: `firstName, lastName, teamNickname, injury, expectedReturn, imageUrl, theme, url` (8 keys, all required-present; `firstName`/`lastName`/`teamNickname` required non-null per the D8 model). 99 entries on the 2026-05-28 seed.

## Tests

- `tests/unit/api/scout/nrlcom_casualty_ward/test_models.py` — always-on D8 drift unit tests against the checked-in fixture (`tests/fixtures/scout/nrlcom_casualty_ward/canonical_response.json`): canonical parse + unknown-top-level / unknown-casualty-field / missing-`teamNickname` negatives. The route strict-parses the response through `NrlcomCasualtyWard` (drift → 500 + failed audit; single-envelope abort, the draw precedent).
- `tests/integration/scout/nrlcom_casualty_ward/test_response_shape.py` — env-flagged (`SCOUT_DRIFT_LIVE=1`) live drift test against the real `/casualty-ward/data` endpoint. Skipped in CI by default. Per D8 the agent does not auto-adapt — a live shape change fails loudly and routes to the operator.
- `tests/unit/scripts/data/populate/test_phase_aux.py` — unit-tests the pure `_casualty_to_row` + `_bucket_status` extractor seams (field mapping, skip-no-name/no-team, Round-N gap → `1_week`/`2_4_weeks`/`4_8_weeks` + `indefinite`/`season`/`training`/`test`).
