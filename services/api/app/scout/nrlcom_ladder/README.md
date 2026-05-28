# Scout / nrl.com Ladder

Per-round team standings + 22 per-team metrics (form, streak, points-for/against, home/away/day/night records, average margins, betting odds).

| Field | Value |
|---|---|
| Source | `nrl.com/ladder/data?competition=&season=[&round=]` |
| Cadence | Daily cron — 18:45 UTC (04:45 AEST) for NRL (comp 111), current season; round resolved server-side. See `scripts/cron.d/jeromelu` |
| Historical reach | ~1990s (29 seasons in filter) — Phase 5 backfill |
| Pipeline label | `nrlcom-ladder` |
| Endpoint | `POST /api/admin/scout/nrlcom-ladder?competition=N&season=Y[&round=N]` |
| Make target | `make scout-nrlcom-ladder COMPETITION=111 SEASON=2026 [ROUND=N]` |
| S3 archive | `scout/nrlcom/ladder/{comp}/{season}/round-{NN}.json` |
| DB extraction | `scripts/data/populate/phase_aux.py:populate_team_standings` — one UPSERT per `(team, comp, season, round)` → `team_standings` (lineage: [data-lineage/team_standings.md](../../../../../docs/operations/data-lineage/team_standings.md)) |

The position object has 6 keys (`clubProfileUrl`, `movement`, `next`, `stats`, `teamNickname`, `theme`) — **no `position` field upstream**; the extractor falls back to the 1-based enumerate index. The `stats` object's 22 metrics use space-separated upstream keys (`"points for"`, `"average winning margin"`, …) which the D8 model maps via `Field(alias=...)` with `populate_by_name=True`.

## Tests

- `tests/unit/api/scout/nrlcom_ladder/test_models.py` — always-on D8 drift unit tests against the checked-in fixture (`tests/fixtures/scout/nrlcom_ladder/canonical_response.json`): canonical parse (proves the space-alias mapping reaches `points_for` / `average_winning_margin` / etc.) + unknown-top-level / unknown-`stats`-key / missing-`teamNickname` negatives. The route strict-parses the response through `NrlcomLadder` (drift → 500 + failed audit; single-envelope abort, the draw precedent).
- `tests/integration/scout/nrlcom_ladder/test_response_shape.py` — env-flagged (`SCOUT_DRIFT_LIVE=1`) live drift test against the real `/ladder/data` endpoint. Skipped in CI by default. Per D8 the agent does not auto-adapt — a live shape change fails loudly and routes to the operator.
- `tests/unit/scripts/data/populate/test_phase_aux.py` — unit-tests the pure `_extract_standing_rows` extractor seam (22-metric space-key→column mapping, team resolution by nickname, `ladder_position` enumerate-index fallback).
