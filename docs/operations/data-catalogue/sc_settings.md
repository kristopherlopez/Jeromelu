---
tags: [area/operations, data-catalogue]
---

# sc_settings

[← Data Catalogue](README.md) · [Lineage](../data-lineage/sc_settings.md) · Layer 2 — Structured world

Per-season snapshot of SuperCoach game rules. The `/api/nrl/classic/v1/settings` endpoint returns deeply-nested JSON (~100 leaf fields covering competition / content / game / system: lockouts, scoring rules, captains config, dual-position rules, currency). Stored as a single JSONB blob since the data isn't queried row-by-row — it's read whole for "explain how SC works" contexts. Added in mig 055.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| season | int | no | | |
| captured_at | timestamptz | no | now() | Wall-clock |
| captured_date | date | no | `(now() AT TIME ZONE 'UTC')::DATE` | Plain column kept consistent with `captured_at` by the writer (generated columns over timestamptz aren't supported by Postgres) |
| mode | text | no | `classic` | `classic` or `draft` |
| payload | jsonb | no | | Whole settings response |
| s3_archive_key | text | yes | | S3 key of the raw archive |
| created_at | timestamptz | no | now() | |

**Unique:** `(season, captured_date, mode)` — one row per (season, day, mode); same-day re-runs UPSERT
**Indexes:** season

Application-side responsibility: keep `captured_date == captured_at::date`. The route helper sets both consistently; conflict resolution uses `captured_date` directly.
