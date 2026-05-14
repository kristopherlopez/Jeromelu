---
tags: [area/operations, data-catalogue]
---

# Migrations

[← Data Catalogue](README.md)

Authoritative list: [`packages/db/migrations/`](../../../packages/db/migrations/). Each filename describes the change; read the SQL for detail.

Recent landmarks worth knowing about:

- **036** — typed identity tables ([people](people.md), [player_attributes](player_attributes.md), [people_roles](people_roles.md), [rounds](rounds.md)) + association junctions ([claim_associations](claim_associations.md), [prediction_associations](prediction_associations.md), [decision_associations](decision_associations.md)) added; [claims](claims.md) absorbed `source_annotations`; [matches](matches.md) accommodates byes; column promotions on teams/venues/matches; `is_captain` on [match_team_lists](match_team_lists.md).
- **037** — dropped two stale postgres-default-named CHECK constraints that conflicted with their `ck_*` replacements.
- **038** — dropped `entities`, `entity_roles`, `player_attributes`; dropped all polymorphic `*_entity_id` columns from output tables; tightened CHECK constraints on [wiki_pages](wiki_pages.md) / [consensus_snapshots](consensus_snapshots.md) / [knowledge_base](knowledge_base.md) to enforce typed-FK exactly-one (or at-most-one for KB).

See [refactor-entities-to-typed-tables](../refactor-entities-to-typed-tables.md) for the full design doc behind 036–038.

When a migration lands:

1. Update the affected per-table file in this folder.
2. Update the schema overview diagram in [README](README.md) if the topology changed.
3. If the migration drops a table, move its description to [deprecated](deprecated.md) with a one-line note pointing at the replacement.
