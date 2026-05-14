---
tags: [area/operations, data-lineage]
---

# Lineage: matches

[Schema: data-catalogue/matches.md](../data-catalogue/matches.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| nrl.com / match-centre | [data-sources/nrlcom/match-centre.md](../data-sources/nrlcom/match-centre.md) | Primary — one match-centre archive becomes one `matches` row |

`matches.source` text column allows `nrl_com`, `supercoach`, `manual` per the schema, but only `nrl_com` is populated by current extractors.

## Extractor

`scripts/data/populate/phase_matches.py` — `populate_matches()` walks `scout/nrlcom/match-centre/{comp}/{season}/round-{NN}/{slug}.json`, does idempotent UPSERT keyed on `(source, season, grade, external_match_id)` per the `uq_matches_source_external` partial unique index.

## Field mapping

| DB column | Source | Source field | Notes |
|---|---|---|---|
| `match_id` | derived | — | UUID, DB-side default |
| `source` | constant | `'nrl_com'` | Hardcoded in extractor |
| `external_match_id` | match-centre | `$.matchId` | Idempotency key. Skipped if missing/blank |
| `season` | S3 key | `scout/.../{season}/...` | Parsed from key path, not payload |
| `round` | S3 key | `scout/.../round-{NN}/...` | Parsed from key path |
| `round_label` | match-centre | `$.roundTitle` | e.g. "Round 7", "Finals Week 1" |
| `grade` | S3 key | `scout/.../{competition}/...` | Mapped via `_GRADE_MAP`: 111→`nrl`, 161→`nrlw`, 113→`nsw_cup`, 114→`qld_cup`, 156→`jersey_flegg`, 155→`mal_meninga`. Default `nrl` |
| `home_team_id` | match-centre | `$.homeTeam.teamId` | Resolved via `teams.nrlcom_team_id`; **row dropped** if no team match |
| `away_team_id` | match-centre | `$.awayTeam.teamId` | Same; row dropped if missing or `home_team_id == away_team_id` (`ck_matches_distinct_teams`) |
| `venue_id` | match-centre | `$.venue` | Fuzzy match on `lower(venues.name)`; NULL on miss (no row dropped) |
| `kickoff_at` | match-centre | `$.startTime` | UTC ISO string, stored as timestamptz |
| `status` | match-centre | `$.matchState` | Mapped via `_STATUS_MAP`: `Upcoming`→`scheduled`, `InProgress`/`Live`→`live`, `FullTime`→`final`, `Postponed`→`postponed`, `Cancelled`→`cancelled`, `Forfeit`→`forfeit`. Default `scheduled` |
| `home_score` | match-centre | `$.homeTeam.score` | Paired with `away_score`: both NULL if either is missing |
| `away_score` | match-centre | `$.awayTeam.score` | Same |
| `weather` | match-centre | `$.weather` | |
| `referee_name` | match-centre | `$.officials[*]` where `position == 'referee'` | Joined `firstName + ' ' + lastName` |
| `broadcast` | not extracted | — | Column exists; always NULL today |
| `attendance` | match-centre | `$.attendance` | NULL if 0 (nrl.com sentinel for unknown attendance) |
| `ground_conditions` | match-centre | `$.groundConditions` | |
| `is_magic_round` | not extracted | — | Always `false` today |
| `is_rep_weekend` | not extracted | — | Always `false` today |
| `metadata_json` | match-centre | mixed | Stashed keys: `competition.competitionId`, `venueCity`, `matchMode`, `hasExtraTime`, `segmentCount`, `segmentDuration` (NULL keys dropped) |
| `last_synced_at` | derived | — | `NOW()` on every UPSERT |
| `created_at` | derived | — | DB default `now()` |
| `updated_at` | derived | — | DB default `now()` (auto-updates) |

## UPSERT semantics

On conflict, only these columns are overwritten:
- `round`, `round_label`, `kickoff_at`, `status`, `home_score`, `away_score`, `weather`, `attendance`, `ground_conditions`, `last_synced_at`

`venue_id` and `referee_name` use `COALESCE(EXCLUDED.x, matches.x)` — won't clobber a known value with NULL on a re-extract.

`metadata_json` is **merged** (`matches.metadata_json || EXCLUDED.metadata_json`) — additive, not replacing.

## Bye rows

The extractor does not currently emit `status='bye'` rows. Match-centre archives don't exist for bye fixtures — those would have to come from `scout/nrlcom/draw/*` (`$.filterRounds[*]` enumerates byes), via a separate path that's not yet built.

## Drift notes (catalogue)

`data-catalogue/matches.md` is missing two columns the extractor populates today:
- `attendance` — added by migration 063
- `ground_conditions` — added by migration 063

Update the catalogue when convenient.
