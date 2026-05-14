---
tags: [area/operations, data-catalogue, status/planned]
---

# squad_slots, squad_trades — planned (SuperCoach squad feature)

[← Data Catalogue](README.md) · [Lineage](../data-lineage/squad_slots.md) · Layer 4 — Reasoning & output

Reserved for the upcoming SuperCoach squad management feature; tables exist but their player FK columns were dropped in mig 038 (they referenced the now-gone `entities` table). Player references return as typed FKs (`player_id` → people) when the SuperCoach feature is built. See [architecture/04-information-architecture.md](../../architecture/04-information-architecture.md).
