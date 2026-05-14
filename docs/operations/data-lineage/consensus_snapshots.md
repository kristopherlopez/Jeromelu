---
tags: [area/operations, data-lineage]
---

# Lineage: consensus_snapshots

[Schema: data-catalogue/consensus_snapshots.md](../data-catalogue/consensus_snapshots.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Aggregation over [claims](claims.md) | — | **Primary** — derived view, not external |

## Writer

Aggregator job (planned/scheduled) that computes per-subject claim sentiment buckets at a point in time. Reads from `claims` + `claim_associations`, GROUP BY (subject typed FK, time bucket).

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `snapshot_id` | derived | UUID, DB-side default |
| `person_id` / `team_id` / `match_id` / `venue_id` / `round_id` | aggregator | Exactly one per row (`ck_consensus_snapshots_subject`) |
| `time_bucket` | aggregator | Aggregation window start (e.g. round-N kickoff) |
| `buy_count`, `sell_count`, `hold_count`, `neutral_count` | aggregator | `COUNT(*) WHERE claim_type IN (...)` over claims with `role='subject'` and matching subject FK |
| `contrarian_score` | aggregator | Derived metric — high when consensus disagrees with outcomes |
| `consensus_score` | aggregator | -1..+1 net polarity of claims |
| `created_at` | derived | DB default `now()` |

## Notes

- Powers ledger / wiki "what does the market think about X right now" cards.
- The aggregator can be re-run for any historical bucket — `claims` are immutable so the derivation is deterministic.
