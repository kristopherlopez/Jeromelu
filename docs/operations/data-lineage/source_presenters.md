---
tags: [area/operations, data-lineage]
---

# Lineage: source_presenters

[Schema: data-catalogue/source_presenters.md](../data-catalogue/source_presenters.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Presenter Miner review queue | — | **Primary** — confirmed presenter associations |

## Writer

`services/api/app/routers/presenters.py` — handles `POST /api/admin/presenters/candidates/{id}/confirm`:
1. Either creates a new [people](people.md) row OR links to an existing `person_id` (from the candidate's `existing_person_id` hint or a manual override on confirm)
2. INSERTs a `source_presenters` row with `(channel_id, person_id, role)`
3. Sets the upstream candidate's `status='confirmed'` and `confirmed_person_id`

Idempotent on `(channel_id, person_id)` — re-confirming the same candidate is a no-op on this constraint.

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `id` | derived | UUID, DB-side default |
| `channel_id` | candidate | FK → channels (CASCADE) |
| `person_id` | candidate / review | FK → people (CASCADE) |
| `role` | candidate / review override | `host`, `co-host`, `regular`, `frequent-guest`. May differ from candidate's role if reviewer overrode on confirm |
| `is_regular` | derived | `true` for host/co-host/regular; `false` for frequent-guest |
| `since_ts` | review | Optional join date if known |
| `confirmed_at` | derived | DB default `now()` |
| `confirmed_by` | review | Reviewer identity |
| `candidate_id` | candidate | FK → miner_presenter_candidates (SET NULL). Provenance pointer |

## Notes

- Anchored at channel level — presenters are a property of the *show*, not the episode.
- See migration 052 and `docs/agents/system/presenter-miner.md`.
