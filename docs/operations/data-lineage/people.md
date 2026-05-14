---
tags: [area/operations, data-lineage]
---

# Lineage: people

[Schema: data-catalogue/people.md](../data-catalogue/people.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| supercoach / classic-players-cf | [data-sources/supercoach/classic-players-cf.md](../data-sources/supercoach/classic-players-cf.md) | **Primary writer for SC-eligible players** — sets `canonical_name`, `slug`, `aliases`, `supercoach_id` |
| nrl.com / match-centre | [data-sources/nrlcom/match-centre.md](../data-sources/nrlcom/match-centre.md) | Inserts historical players, coaches, referees missing from SC; merges `nrlcom_player_id` onto existing rows |
| nrl.com / players-roster | [data-sources/nrlcom/players-roster.md](../data-sources/nrlcom/players-roster.md) | Enriches `image_url`, `dob`, `country` on existing rows |

## Extractors

- `services/api/app/scout/supercoach_roster/` — SC roster fetcher; primary writer for SC-eligible players
- `scripts/data/populate/phase_people.py` — `populate_people_history()`, walks every match-centre archive; INSERTs net-new profile ids (players + coaches + officials), merges into existing rows by name + current team
- `scripts/data/populate/phase_identity.py` — `backfill_identity()` walks 2024-2026 match-centre and UPDATEs `nrlcom_player_id` onto rows already inserted by other writers

## Field mapping

| DB column | Source | Source field | Notes |
|---|---|---|---|
| `person_id` | derived | — | UUID, DB-side default |
| `canonical_name` | SC players-cf | `firstName + ' ' + lastName` | SC primary; nrlcom fills in for non-SC people |
| `aliases` | SC players-cf / manual | various | Alternative spellings |
| `slug` | derived | `slugify(canonical_name)` | Falls back to `<base>-<nrlcom_id>` on collision |
| `dob` | nrl.com players-roster | profile `dob` field | Enrichment pass |
| `country` | nrl.com players-roster | profile `country` field | |
| `image_url` | nrl.com match-centre | `$.{home,away}Team.players[*].headImage` ⊕ `coaches[*].headImage` ⊕ `officials[*].headImage` | First-match-wins per profile id; updated via `COALESCE` (won't clobber) |
| `supercoach_id` | SC players-cf | `id` | UNIQUE; NULL for non-SC players |
| `metadata_json` | mixed | — | `nrlcom_url`, `role_class` (`player`/`coach`/`referee`), `source` (`nrlcom/match-centre`), other long-tail |
| `nrlcom_player_id` | nrl.com match-centre | `$.{home,away}Team.players[*].playerId` ⊕ `coaches[*].profileId` ⊕ `officials[*].profileId` | UNIQUE; one identity space across players/coaches/officials |
| `created_at` | derived | — | DB default `now()` |

## Resolution rules (phase_people)

For each distinct `nrlcom_player_id` seen in match-centre:
1. If `nrlcom_player_id` already on a row → no-op
2. Else if a row exists with matching `canonical_name` + current team (via `player_attributes` SCD-2) AND that row has `nrlcom_player_id IS NULL` → UPDATE that row, merging IDs (also fills `image_url` via COALESCE, appends `nrlcom_url` to `metadata_json`)
3. Else INSERT new row with `slug = slugify(name)` (or `<slug>-<nrlcom_id>` on collision)

`nrl.com` star-runs (`***`) are stripped from name fields before matching/insertion.

## Notes

- Three sources don't share player IDs. `people` is the merge point. Cross-source IDs (`supercoach_id`, `nrlcom_player_id`) live on the same row.
- `nrlsupercoachstats` is deliberately skipped as a writer — its IDs are name-hashes, not safe as identity keys. Used only for historical stats backfill.
- Casualty-ward never inserts; only used for enrichment via the `injuries` extractor.
