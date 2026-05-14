---
tags: [area/operations, data-catalogue, status/deprecated]
---

# Deprecated / removed

[← Data Catalogue](README.md)

Tables that have been dropped by migrations and what replaced them.

## player_team_history

Dropped in migration 027. Replaced by [player_attributes](player_attributes.md) (mig 027) and subsequently by [player_attributes](player_attributes.md) (mig 038).

## entities

Dropped in migration 038. The polymorphic identity hub is replaced by typed per-kind tables: [people](people.md) (humans), [rounds](rounds.md) (NRL fixture rounds), and the existing structured-world tables ([teams](teams.md), [venues](venues.md), [matches](matches.md)). Cross-type references that previously used `entity_id` go through typed-FK association junctions ([claim_associations](claim_associations.md), [prediction_associations](prediction_associations.md), [decision_associations](decision_associations.md)) or direct typed FKs (`speaker_person_id`, `predictor_person_id`, `player_id`, etc.).

## entity_roles

Dropped in migration 038. Replaced by [people_roles](people_roles.md) — same SCD-2 shape with `person_id` FK to `people` instead of `entity_id` to `entities`.

## player_attributes (old)

Dropped in migration 038. Replaced by [player_attributes](player_attributes.md) — same SCD-2 shape with `person_id` FK to `people`. Generalised to any person role (not just players), though the dominant case is still players.

## source_annotations

Dropped in migration 036. Created in mig 034 (with no production rows), absorbed into a generalised [claims](claims.md) table when it became clear annotations and claims were doing the same job. Annotation kinds (`mention`, `theme`, `subtopic`, `sentiment`, `tactical_tag`, `highlight`) became valid `claim_type` values; `payload_json` was added to `claims` for kind-specific payloads.
