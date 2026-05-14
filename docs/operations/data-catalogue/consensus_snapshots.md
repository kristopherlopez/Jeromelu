---
tags: [area/operations, data-catalogue]
---

# consensus_snapshots

[← Data Catalogue](README.md) · Layer 4 — Reasoning & output

Aggregated claim sentiment for a typed subject at a point in time. Exactly one of `person_id` / `team_id` / `match_id` / `venue_id` / `round_id` is set per row.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| snapshot_id | UUID | PK | uuid4 | |
| person_id | UUID | yes | | FK → people |
| team_id | UUID | yes | | FK → teams |
| match_id | UUID | yes | | FK → matches |
| venue_id | UUID | yes | | FK → venues |
| round_id | UUID | yes | | FK → rounds |
| time_bucket | timestamptz | no | | Aggregation window |
| buy_count | int | no | 0 | |
| sell_count | int | no | 0 | |
| hold_count | int | no | 0 | |
| neutral_count | int | no | 0 | |
| contrarian_score | float | yes | | |
| consensus_score | float | yes | | |
| created_at | timestamptz | no | now() | |

**Check:** exactly-one of typed FKs (`ck_consensus_snapshots_subject`)
**Indexes:** (person_id, time_bucket)
**FK:** person_id → people; team_id → teams; match_id → matches; venue_id → venues; round_id → rounds
