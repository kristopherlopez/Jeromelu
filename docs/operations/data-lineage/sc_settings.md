---
tags: [area/operations, data-lineage]
---

# Lineage: sc_settings

[Schema: data-catalogue/sc_settings.md](../data-catalogue/sc_settings.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| supercoach / classic-settings | [data-sources/supercoach/classic-settings.md](../data-sources/supercoach/classic-settings.md) | **Primary** — `mode='classic'` rows |
| supercoach / draft-settings | [data-sources/supercoach/draft-settings.md](../data-sources/supercoach/draft-settings.md) | `mode='draft'` rows |

## Writer

`services/api/app/miner/supercoach_settings/` — fetcher hits the `/api/nrl/classic/v1/settings` (and draft equivalent) endpoints, archives to S3, then UPSERTs the whole payload as JSONB.

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `id` | derived | UUID, DB-side default |
| `season` | writer (URL param) | NRL season the settings apply to |
| `captured_at` | derived | DB default `now()` |
| `captured_date` | writer | Plain column kept consistent with `captured_at::date` by the writer (Postgres won't allow generated cols over timestamptz casts) |
| `mode` | writer | `classic` or `draft` |
| `payload` | SC settings response | Whole nested JSON (~100 leaf fields covering competition / content / game / system) |
| `s3_archive_key` | writer | The raw S3 key for traceability |
| `created_at` | derived | DB default `now()` |

## UPSERT semantics

Unique on `(season, captured_date, mode)`. Same-day re-runs UPSERT — the first daily snapshot stays as the canonical state for that day.

## Notes

- Stored whole rather than flattened because the data isn't queried row-by-row — it's read whole for "explain how SC works" contexts.
- See migration 055.
