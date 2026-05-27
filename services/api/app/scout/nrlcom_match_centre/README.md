# Scout / nrl.com Match Centre

The highest-leverage pipeline. One call per match yields the full per-match record:
- 19-player squads with playerId, jersey, position, on-field flag, bodyImage, headImage, club URL
- positionGroups mapping (Backs/Forwards/Interchange/Reserves/Coaches → home/away playerIds)
- Per-player ~58-field match stat line (`stats.players.homeTeam[]` / `.awayTeam[]`)
- 100+ typed timeline events (Try, Goal, Penalty, SetRestart, etc.) with gameSeconds
- Officials (referee + touch judges + bunker)
- Coaches per team
- Scoring narrative (tries/conversions/penalty-goals with player + minute)
- Match identity: matchId, score, venue, attendance, weather, broadcast, segments

| Field | Value |
|---|---|
| Source | `nrl.com/draw/{league}/{season}/round-{N}/{slug}/data/` per match |
| Cadence | Daily cron (current round, 18:15 UTC); per-match immutable post-FullTime |
| Historical reach | 1990 thin / 2000+ full (60-91KB per match) |
| Pipeline label | `nrlcom-match-centre` |
| Endpoint | `POST /api/admin/scout/nrlcom-match-centre?competition=N&season=Y[&round=N]` (round omitted → current round, resolved from the draw's `selectedRoundId`) |
| Make target | `make scout-nrlcom-match-centre COMPETITION=111 SEASON=2026 [ROUND=N]` |
| S3 archive | `scout/nrlcom/match-centre/{comp}/{season}/round-{NN}/{slug}.json` |
| DB extraction | **Deferred** — Phase 3.5: writes match_team_lists, player_match_stats, match_timeline, match_officials |

## How it works

1. Calls the draw endpoint for (competition, season, round) to discover fixtures.
2. For each fixture, walks the `matchCentreUrl` slug → fetches `https://www.nrl.com{matchCentreUrl}data/`.
3. Archives each match's JSON to S3 under the slug-keyed path.
4. Returns counts: matches_fetched, archive_failures.

Rate-limited at 1 req/sec to nrl.com per request to be polite.

## What 2026 R7 wests-tigers-v-broncos looks like (91KB)

Top-level keys: `animateMatchClock, attendance, awayTeam, broadcastChannels,
competition, gameSeconds, groundConditions, hasExtraTime, hasOnFieldTracking,
homeTeam, imageUrl, matchId, matchMode, matchState, officials, positionGroups,
roundNumber, roundTitle, segmentCount, segmentDuration, showPlayerPositions,
showTeamPositions, startTime, stats, timeline, updated, url, venue, venueCity, weather`

Inside `stats`: per-player 58-field stat lines + match-level team aggregates + top-performers leaderboards.

## D8 envelope is match-state-dependent

The top-level key set differs by `matchState` (verified live): a **FullTime** match carries `attendance`, `officials`, `positionGroups`, `timeline`, `weather`, `groundConditions`, `imageUrl`; an **Upcoming** match omits those and instead carries `broadcastChannels`, `videoProviders`; 22 keys are shared. `NrlcomMatchCentre` (envelope-only, `extra="forbid"`) is therefore a **union** — 22 shared keys required, the state-dependent keys optional — so both states validate while a genuinely new top-level section still trips the guard. Deep internals (stats/timeline/lineups) stay opaque; the DB extractors (Phase 3.5) read them.

## Tests

- `tests/unit/api/scout/nrlcom_match_centre/test_models.py` — always-on D8 drift unit tests against two fixtures (`canonical_response.json` = FullTime, `canonical_response_upcoming.json` = Upcoming): both states parse, unknown-top-level + missing-`matchId` negatives raise. The route strict-parses each archived match through `NrlcomMatchCentre`; a `ValidationError` is logged to `validation_failures` **without aborting** the round walk.
- `tests/integration/scout/nrlcom_match_centre/test_response_shape.py` — env-flagged (`SCOUT_DRIFT_LIVE=1`) live drift test against a real match resolved from the draw. Skipped in CI by default. Per D8 the agent does not auto-adapt.
