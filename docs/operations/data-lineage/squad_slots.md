---
tags: [area/operations, data-lineage, status/planned]
---

# Lineage: squad_slots / squad_trades — planned

[Schema: data-catalogue/squad_slots.md](../data-catalogue/squad_slots.md)

## Status

Reserved for the upcoming SuperCoach squad management feature ([[project_v1_scope]] defers SC gameplay to V2). Tables exist in the schema but their player FK columns were dropped in mig 038 (they referenced the now-gone `entities` table).

## Planned writers

- User squad-management UI — INSERT/UPDATE/DELETE squad slots as the user picks players, makes trades, sets captain
- Trade proposal pipeline — INSERTs `squad_trades` rows for each proposed swap (linked to a [decisions](decisions.md) row of `decision_type='trade'`)

## Planned mapping

Player references will return as typed FKs (`player_id` → people) when the SuperCoach feature is built. See `docs/architecture/01-information-architecture.md`.
