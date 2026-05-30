---
tags: [area/operations, data-lineage]
---

# Lineage: teams

[Schema: data-catalogue/teams.md](../data-catalogue/teams.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Seed (one-shot per season) | — | **Primary** — baseline 19 NRL + 12 NRLW + 12 NSW Cup + 15 Hostplus Cup rows |
| supercoach / classic-teams | [data-sources/supercoach/classic-teams.md](../data-sources/supercoach/classic-teams.md) | Enriches `metadata_json.supercoach` (id, abbrev, feed_name, competition) |
| nrl.com / match-centre + draw | [data-sources/nrlcom/match-centre.md](../data-sources/nrlcom/match-centre.md) | Backfills `nrlcom_team_id` onto seeded rows |

## Writers

- **Migration 039** — `039_seed_teams_2026.sql` is the baseline seed (idempotent, `ON CONFLICT (slug) DO UPDATE`)
- **`scripts/data/seed_teams.py`** — yaml-driven seeder for ad-hoc top-ups (PNG team name announcement, feeder affiliation changes)
- **Admin endpoint** — `POST /api/admin/teams/seed` (`make prod-seed-teams`) takes a yaml-shaped JSON payload, runs the same idempotent upsert via `jeromelu_shared.teams.seed_teams()`
- **`scripts/data/populate/phase_identity.py`** — `backfill_identity()` walks match-centre archives and UPDATEs `nrlcom_team_id` onto seeded rows (matched by lower(slug/short_name/aliases) against nrl.com nickname)
- **`services/api/app/miner/supercoach_teams/`** — populates `metadata_json.supercoach`

## Field mapping

| DB column | Source | Source field | Notes |
|---|---|---|---|
| `team_id` | derived | — | UUID, DB-side default |
| `slug` | seed | yaml/manual | UNIQUE; e.g. `brisbane_broncos` |
| `name` | seed | yaml/manual | |
| `short_name` | seed | yaml/manual | |
| `aliases` | seed | yaml/manual | |
| `grade` | seed | yaml/manual | `nrl`, `nrlw`, `nsw_cup`, etc. |
| `competition` | seed | yaml/manual | e.g. `NRL Premiership` |
| `parent_team_id` | seed | yaml/manual | Self-FK; feeder team → senior NRL/NRLW |
| `founded_year` | seed | yaml/manual | |
| `logo_url` | seed | yaml/manual | |
| `metadata_json.supercoach` | SC classic-teams | `{id, abbrev, feed_name, name, competition}` | |
| `metadata_json.enters_competition_year` | seed | yaml/manual | Marks Perth Bears 2027, PNG 2028 expansion sides |
| `metadata_json.lifespan` | manual (interim) | array of stints | For historical clubs (defunct, mergers); see catalogue notes |
| `nrlcom_team_id` | nrl.com match-centre | `$.{home,away}Team.teamId` | Backfilled by `phase_identity` (mig 062 added column) |
| `active` | seed | yaml/manual | Defaults true; false for defunct clubs |
| `created_at` | derived | — | |
| `updated_at` | derived | — | Auto-updates |

## Notes

- Pathway grades (Jersey Flegg, SG Ball, Mal Meninga, Cyril Connell, Harold Matthews) are schema-allowed but not yet seeded.
- Historical lineage (defunct clubs, mergers, competition renames) lives in `metadata_json` per the interim convention documented in the catalogue.
