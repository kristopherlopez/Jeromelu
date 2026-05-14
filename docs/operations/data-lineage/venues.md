---
tags: [area/operations, data-lineage]
---

# Lineage: venues

[Schema: data-catalogue/venues.md](../data-catalogue/venues.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Seed (`data/venues.yaml`) | — | **Primary** — all rows |

## Writers

- **`scripts/data/seed_venues.py`** — `make seed-venues`. Idempotent yaml-driven seeder; reads `data/venues.yaml` and upserts on `slug`.

## Field mapping

All columns are sourced from `data/venues.yaml` per row. There is no extractor pulling venues from external feeds today.

| DB column | Source | Notes |
|---|---|---|
| `venue_id` | derived | UUID, DB-side default |
| `slug` | yaml | UNIQUE; e.g. `suncorp_stadium` |
| `name` | yaml | Current sponsored name |
| `aliases` | yaml | Sponsorship history + colloquial names; used for fuzzy match by [matches](matches.md) extractor |
| `city`, `state`, `country` | yaml | |
| `capacity` | yaml | |
| `surface`, `roof` | yaml | |
| `tz` | yaml | IANA timezone |
| `latitude`, `longitude` | yaml | |
| `opened_year` | yaml | |
| `image_url` | yaml | |
| `metadata_json` | yaml | Long-tail keys |
| `active` | yaml | Defaults true |
| `created_at` | derived | |
| `updated_at` | derived | Auto-updates |

## Drift handling

The `matches` extractor fuzzy-matches on `lower(venues.name)`. Misses leave `matches.venue_id = NULL` — discoverable by querying `WHERE venue_id IS NULL`. When new venues appear in match-centre (one-off Magic Round venues, country trials), add to `data/venues.yaml` and re-seed.
