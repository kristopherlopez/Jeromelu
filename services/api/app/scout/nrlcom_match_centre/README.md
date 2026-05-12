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
| Cadence | Per-match post-FullTime (immutable after game ends) |
| Historical reach | 1990 thin / 2000+ full (60-91KB per match) |
| Pipeline label | `nrlcom-match-centre` |
| Endpoint | `POST /api/admin/scout/nrlcom-match-centre?competition=N&season=Y&round=N` |
| Make target | `make scout-nrlcom-match-centre COMPETITION=111 SEASON=2026 ROUND=N` |
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
