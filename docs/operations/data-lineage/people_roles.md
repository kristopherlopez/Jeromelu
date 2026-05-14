---
tags: [area/operations, data-lineage]
---

# Lineage: people_roles

[Schema: data-catalogue/people_roles.md](../data-catalogue/people_roles.md)

## Status

No external-feed extractor writes to this table today. Rows exist from:

- **Mig 036 backfill** — `source='backfill_036'` rows projected from the prior `entity_roles` table when the typed-identity refactor ran
- **Manual / seed** — `source='seed'` or `'manual'` for known commentators/journalists/advisors

## Future writers (planned)

- **Coach role tenure from match-centre** — `phase_people` already inserts coaches into [people](people.md) with `metadata_json.role_class='coach'`. A follow-up phase should project their match-centre appearances into `people_roles` rows (`role='coach'`, tenure = first/last match seen for that team).
- **Commentator/journalist roles from Analyst** — diarisation against podcast/YouTube transcripts identifies recurring voices; confirmed presenters via [source_presenters](source_presenters.md) can drop a `people_roles` row with `role='commentator'`.

## Field mapping (writer-agnostic)

| DB column | Source | Notes |
|---|---|---|
| `role_id` | derived | UUID, DB-side default |
| `person_id` | resolved | FK to people |
| `role` | writer | `player`, `coach`, `commentator`, `journalist`, `referee`, `advisor` |
| `effective_from` | writer | Start of tenure |
| `effective_to` | writer | NULL = current; closed-out value when role ends |
| `is_primary` | writer | Exactly one primary current row per person enforced by unique partial index |
| `metadata_json` | writer | Long-tail per role |
| `source` | writer | `seed`, `backfill_036`, `manual`, future: `nrlcom/match-centre`, `analyst/diarisation` |
| `created_at` | derived | DB default `now()` |
| `updated_at` | derived | Auto-updates |

## Notes

- Multi-valued at a single point in time — Adam Reynolds = active player + occasional commentator both rows; Andrew Johns transition = player closed + commentator open.
- The `is_primary` column matters for "what is this person's headline role" queries.
