# Scout / nrl.com Draw

Captures fixture data per round.

| Field | Value |
|---|---|
| Source | `nrl.com/draw/data?competition=&season=&round=` |
| Cadence | Daily cron (current round, 18:00 UTC); also backfill for historical seasons |
| Historical reach | 1908 (filterSeasons has 119 entries) |
| Pipeline label | `nrlcom-draw` |
| Endpoint | `POST /api/admin/scout/nrlcom-draw?competition=N&season=Y[&round=N]` |
| Make target | `make scout-nrlcom-draw COMPETITION=111 SEASON=2026 [ROUND=N]` |
| S3 archive | `scout/nrlcom/draw/{comp}/{season}/round-{NN}.json` |
| DB extraction | **Deferred** — downstream extractor reads S3 → writes `matches`, `rounds` |

NRL premiership = competition `111`. NRLW / NSW Cup / QLD Cup have other comp IDs.

If `round` is omitted, the response contains the *current* round's fixtures + all filter metadata.

## Tests

- `tests/unit/api/scout/test_nrlcom_draw_models.py` — always-on D8 drift unit tests against the checked-in fixture (`tests/fixtures/scout/nrlcom_draw/canonical_response.json`): canonical parse + unknown-top-level / unknown-fixture-field / missing-`matchCentreUrl` negatives. The route strict-parses the response through `NrlcomDraw` (drift → 500 + failed audit).
- `tests/integration/scout/test_nrlcom_draw_response_shape.py` — env-flagged (`SCOUT_DRIFT_LIVE=1`) live drift test against the real `/draw/data` endpoint. Skipped in CI by default. Per D8 the agent does not auto-adapt — a live shape change fails loudly and routes to the operator.
