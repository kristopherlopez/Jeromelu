# Miner / nrl.com Players Roster

Per-team player profile listings from nrl.com — name, position, profile URL, body image. Complements the SC roster (which has SC-specific position eligibility + price).

| Field | Value |
|---|---|
| Source | `nrl.com/players/data?competition=&team={team_id}` |
| Cadence | **Weekly Mondays 23:40 UTC** (Tuesday 09:40 AEST), `scripts/cron.d/jeromelu`. Cron calls the `refresh-all` endpoint below. |
| Pipeline label | `nrlcom-players-roster` (per-team) · `nrlcom-players-roster-refresh-all` (envelope for the 17-team walk) |
| Per-team endpoint | `POST /api/admin/miner/nrlcom-players-roster?competition=N&team={team_id}` |
| Bulk endpoint | `POST /api/admin/miner/nrlcom-players-roster/refresh-all?competition=N` — walks the 17 NRL teams server-side at 1 req/sec (~20s wall time); non-aborting per-team (errors land in the response body, HTTP status stays 200) |
| Make targets | `make miner-nrlcom-players-roster TEAM=500021` (per-team; e.g. Storm). No make target for refresh-all — cron and operators hit the endpoint directly. |
| S3 archive | `miner/nrlcom/players-roster/{comp}/team-{team_id}.json` (one key per team; overwrites each refresh) |
| DB extraction | **No JSON-side extractor ships in Phase 4.5** — the existing HTML-scrape enrichment at `jeromelu_shared/players/nrlcom_refresh.py` (which hits the per-player profile **PAGES**, a different endpoint) is untouched per the scope decision. A future phase can build a JSON-side extractor that reads these archives. |

## NRL team_id catalogue

The 17 NRL.com internal `team_id` values + theme short names live in `services/api/app/miner/nrlcom_players_roster/teams.py` as `NRL_TEAM_IDS: list[tuple[str, int]]`. They were derived from the canonical fixture's `filterTeams[]` (the `/players/data` response itself carries the full catalogue, so a single live fetch yields the walk-set without S3 dependency).

Spot-checked values: **Broncos=500011, Storm=500021, Dolphins=500723, Wests Tigers=500023, Warriors=500032** etc. The README's prior example incorrectly labelled `team=500011` as Storm (it's Broncos) — corrected in this commit.

When a new club joins, refresh the canonical fixture (rerun the TASK-31 live-capture path) and re-derive `NRL_TEAM_IDS` from `data["filterTeams"]`.

## D8 drift contract

Strict-parse via `models.py`:

| Model | Strictness target |
|---|---|
| `NrlcomPlayersRoster` (envelope) | 6 keys: `profileGroups`, `filterCompetitions`, `filterTeams`, `isClubSite`, `selectedCompetitionId`, `selectedTeamId` |
| `ProfileGroup` | 2 keys: `title` (observed `""` empty), `profiles` |
| `Profile` | 7 flat keys: `firstName`, `lastName`, `teamNickName`, `position`, `url`, `bodyImage`, `theme`. All required-present-but-nullable; `theme` opaque (`dict[str, Any] | None`) since no extractor reads into it this phase. |

The strictness boundary stops at the identity-field level because no DB extractor reads `/players/data` yet (S3-only this phase). If a future extractor lands, identity-field types should tighten to `str` (non-null) per the casualty/ladder precedent.

## Tests

- **Unit (CI):** `pytest tests/unit/api/miner/nrlcom_players_roster/test_models.py` — 4 cases (canonical parse + 3 negatives).
- **Live drift (env-flagged):** `MINER_DRIFT_LIVE=1 pytest tests/integration/miner/nrlcom_players_roster/test_response_shape.py` — hits real nrl.com (`team=500011`); fails loudly with the offending field name on drift.
- **Route strict-parse:** both per-team and refresh-all routes invoke `NrlcomPlayersRoster.model_validate(data)` after S3 archive; `detail["validated"] = True` on success; `ValidationError → HTTPException(500)`.
