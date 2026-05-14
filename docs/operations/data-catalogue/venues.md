---
tags: [area/operations, data-catalogue]
---

# venues

[← Data Catalogue](README.md) · Layer 2 — Structured world

Stadium reference table. Slow-changing — roughly 25–30 NRL/NRLW grounds plus
the occasional one-off (Magic Round host city, country trial venues).
Referenced by `matches.venue_id`.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| venue_id | UUID | PK | uuid4 | |
| slug | text | no | | UNIQUE; e.g. `suncorp_stadium`, `accor_stadium` |
| name | text | no | | Current sponsored name |
| aliases | text[] | no | `{}` | Sponsorship history + colloquial names; used for fuzzy match on ingest |
| city | text | yes | | |
| state | text | yes | | NULL for non-AU venues |
| country | text | no | `AU` | ISO-style country code (`AU`, `NZ`) |
| capacity | int | yes | | |
| surface | text | yes | | `grass`, `hybrid`, `synthetic` |
| roof | text | yes | | `open`, `closed`, `retractable` |
| tz | text | yes | | IANA timezone (`Australia/Brisbane`, `Australia/Sydney`, `Pacific/Auckland`); QLD venues do NOT observe DST |
| latitude | numeric(9,6) | yes | | |
| longitude | numeric(9,6) | yes | | |
| opened_year | int | yes | | |
| image_url | text | yes | | |
| metadata_json | jsonb | no | {} | Long-tail (transport_links, parking_capacity, naming_history) |
| active | bool | no | true | |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | Auto-updates |

**Unique:** slug
**Indexes:** active, (country, state)

Seeded from `data/venues.yaml` via `make seed-venues` (script: `scripts/data/seed_venues.py`). Idempotent.
