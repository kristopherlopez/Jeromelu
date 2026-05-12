# Scout / nrl.com Stats Leaderboards

| Field | Value |
|---|---|
| Source | `nrl.com/stats/data?competition=&season=` |
| Cadence | Weekly post-round |
| Pipeline label | `nrlcom-stats` |
| Endpoint | `POST /api/admin/scout/nrlcom-stats?competition=N&season=Y` |
| Make target | `make scout-nrlcom-stats COMPETITION=111 SEASON=2026` |
| S3 archive | `scout/nrlcom/stats/{comp}/{season}.json` |
| DB extraction | **Deferred** — Phase 4.5: writes `stat_leaderboards` (new) |

Returns 8 player-stat groups × 5 sub-groups + 8 team-stat groups, each with top-25 leaders. ~275KB.
