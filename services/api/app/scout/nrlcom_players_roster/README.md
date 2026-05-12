# Scout / nrl.com Players Roster

Per-team player profile listings from nrl.com — DOB, image, position, profile URL. Complements the SC roster (which has SC-specific position eligibility + price).

| Field | Value |
|---|---|
| Source | `nrl.com/players/data?competition=&team={team_id}` |
| Cadence | Weekly |
| Pipeline label | `nrlcom-players-roster` |
| Endpoint | `POST /api/admin/scout/nrlcom-players-roster?competition=N&team={team_id}` |
| Make target | `make scout-nrlcom-players-roster COMPETITION=111 TEAM=500011` |
| S3 archive | `scout/nrlcom/players-roster/{comp}/team-{team_id}.json` |
| DB extraction | **Existing partial** — `jeromelu_shared.players.nrlcom_refresh` enriches `people` with DOB, height, weight, image, birthplace. Will fold into a proper extractor in Phase 4.5. |

`team_id` is the NRL.com internal team ID (e.g. Storm=500011). These appear in the `/draw/data` response's `homeTeam.teamId` / `awayTeam.teamId`, or in `/ladder/data` per team. Walk teams individually — this endpoint is per-team.
