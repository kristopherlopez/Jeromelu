# Miner / nrl.com Stats Leaderboards

| Field | Value |
|---|---|
| Source | `nrl.com/stats/data?competition=&season=` |
| Cadence | **Daily 18:50 UTC** (04:50 AEST), `scripts/cron.d/jeromelu` |
| Pipeline label | `nrlcom-stats` |
| Endpoint | `POST /api/admin/miner/nrlcom-stats?competition=N&season=Y` |
| Make target | `make miner-nrlcom-stats COMPETITION=111 SEASON=2026` |
| S3 archive | `miner/nrlcom/stats/{comp}/{season}.json` |
| DB extraction | ✅ `scripts/data/populate/phase_aux.py:populate_stat_leaderboards` writes `stat_leaderboards` (UPSERT on `(competition, season, scope, category, subgroup, stat_title, leader_position)`) — **manual** for now via `python -m scripts.data.populate_db_from_s3 --phase leaderboards --competition 111` (cron-scheduled extractor is the cross-cutting Phase 4 follow-up, not Phase 4.5 scope) |

Returns 8 player-stat groups × multiple subgroups + 8 team-stat groups (~70 subgroups total), each with top-N leaders (~5 observed live; configurable upstream). Envelope ~275-295KB.

## D8 drift contract

Strict-parse to four levels via `models.py`:

| Model | Strictness target |
|---|---|
| `NrlcomStats` (envelope) | 6 keys: `playerStats`, `teamStats`, `filterCompetitions`, `filterSeasons`, `selectedCompetitionId`, `selectedSeasonId` |
| `StatCategory` (one of `<scope>Stats[]`) | 2 keys: `title` + `groups` |
| `StatSubgroup` (one of `groups[]`) | 4 keys: `title`, `statId`, `leaders`, `url` |
| `StatLeader` (one of `leaders[]`) | 7 universal keys required-present-but-nullable (`played`, `playerId`, `teamId`, `teamName`, `teamNickName`, `theme`, `value`) + 4 player-only fields defaulted `None` (`firstName`, `lastName`, `headImage`, `bodyImage`) + `url` defaulted `None`. Single model handles both player-scope and team-scope leaders (team leaders legitimately omit the player-only keys; same pattern as `NrlcomDraw.videoProviders`). `value` is `str` upstream — extractor coerces via `float()`. |

The strictness mirrors what the extractor reads — `<scope>Stats[].title`, `groups[].title/statId`, `leaders[].firstName/lastName/teamNickName/teamName/playerId/value`. Adding to or renaming any of these trips drift loudly per the D8 contract; the agent does not auto-adapt.

## Tests

- **Unit (CI):** `pytest tests/unit/api/miner/nrlcom_stats/test_models.py` — 4 cases (canonical parse + 3 negatives: unknown top-level, unknown leader-level, missing required category `title`).
- **Live drift (env-flagged):** `MINER_DRIFT_LIVE=1 pytest tests/integration/miner/nrlcom_stats/test_response_shape.py` — hits real nrl.com; fails loudly with the offending field name on drift.
- **Route strict-parse:** `services/api/app/miner/nrlcom_stats/routes.py` invokes `NrlcomStats.model_validate(data)` after S3 archive; sets `detail["validated"] = True` on success. `ValidationError` → `HTTPException(500)` with the drift in the message; raw payload is already in S3 so a validation failure never loses the capture.
- **Extractor pure seam:** `tests/unit/scripts/data/populate/test_phase_leaderboards.py` — 6 cases over `_extract_leader_rows` (field mapping; person-id resolution; team-scope always None; float coercion; nickname lookup with `teamName` fallback; canonical-fixture round trip).
