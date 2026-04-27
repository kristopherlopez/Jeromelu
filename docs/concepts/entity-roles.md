# Entity Roles

Status: **Live** (migration `018_entity_roles.sql`)

People in the NRL move between roles. Players retire and become commentators.
Coaches do TV work in the off-season. Journalists become podcast hosts. We model
this with **one entity per person, many role tenures** — not one entity per role.

---

## Schema

```
entities                      entity_roles (SCD-2)
─────────                     ────────────
entity_id                     entity_role_id
entity_type   ◀────denorm─── role           (current primary role)
canonical_name                effective_from
slug                          effective_to   (NULL = current)
metadata_json                 is_primary     (drives wiki page route)
                              metadata_json  (team for player, network for commentator…)
                              source
```

`entity_type` on `entities` is a **denormalised pointer** — it equals the role
on the `entity_roles` row where `is_primary = TRUE AND effective_to IS NULL`.
Keeping it on `entities` lets existing routes (`/wiki/player/...`,
`/wiki/advisor/...`) and joins (`WHERE entity_type = 'player'`) keep working
without a join.

A partial unique index enforces "exactly one primary current role per entity":

```sql
CREATE UNIQUE INDEX uq_entity_roles_primary_current
  ON entity_roles(entity_id)
  WHERE is_primary AND effective_to IS NULL;
```

---

## Worked examples

### Sequential — Andrew Johns

Played for Newcastle (1995-2007), now a Channel 9 commentator.

```
entities
  entity_id: aj-001
  entity_type: 'commentator'    -- current primary
  canonical_name: 'Andrew Johns'

entity_roles
  ┌──────────────┬─────────────┬─────────────┬───────────┬──────────────────────┐
  │ role         │ from        │ to          │ primary   │ metadata             │
  ├──────────────┼─────────────┼─────────────┼───────────┼──────────────────────┤
  │ player       │ 1995-03-01  │ 2007-09-01  │ false     │ team: knights        │
  │ commentator  │ 2008-01-01  │ NULL        │ true      │ network: channel-9   │
  └──────────────┴─────────────┴─────────────┴───────────┴──────────────────────┘
```

The wiki page lives at `/wiki/commentator/andrew-johns`. A `## Playing Career`
section sources from the closed `player` role row.

### Concurrent — Michael Ennis

Dragons assistant coach + Fox Sports commentator at the same time.

```
entities
  entity_id: me-001
  entity_type: 'coach'    -- pick whichever role dominates the content we ingest

entity_roles
  ┌──────────────┬─────────────┬─────────────┬───────────┬──────────────────────────────────┐
  │ role         │ from        │ to          │ primary   │ metadata                         │
  ├──────────────┼─────────────┼─────────────┼───────────┼──────────────────────────────────┤
  │ player       │ 2003-01-01  │ 2017-09-01  │ false     │ team: broncos                    │
  │ coach        │ 2018-01-01  │ NULL        │ true      │ team: dragons, role: assistant   │
  │ commentator  │ 2017-01-01  │ NULL        │ false     │ network: fox-sports              │
  └──────────────┴─────────────┴─────────────┴───────────┴──────────────────────────────────┘
```

Two open roles, one is primary. The wiki page calls out both — "Currently:
Dragons assistant coach + Fox commentator." Quote attribution from a Fox
broadcast still resolves to this entity.

### Active player + occasional guest — Adam Reynolds

```
entities
  entity_id: ar-001
  entity_type: 'player'

entity_roles
  ┌──────────────┬─────────────┬─────────────┬───────────┬──────────────────────────────────┐
  │ role         │ from        │ to          │ primary   │ metadata                         │
  ├──────────────┼─────────────┼─────────────┼───────────┼──────────────────────────────────┤
  │ player       │ 2011-01-01  │ NULL        │ true      │ team: broncos                    │
  │ commentator  │ 2024-01-01  │ NULL        │ false     │ appearance: guest, network: fox  │
  └──────────────┴─────────────┴─────────────┴───────────┴──────────────────────────────────┘
```

---

## Role transition pattern

When a person's primary role changes (e.g. a player retires and starts
commentating), do this in a transaction:

```sql
-- 1. Close the old primary
UPDATE entity_roles
SET effective_to = '2026-09-01', is_primary = FALSE, updated_at = now()
WHERE entity_id = $1 AND is_primary AND effective_to IS NULL;

-- 2. Open the new primary
INSERT INTO entity_roles (entity_id, role, effective_from, is_primary, source)
VALUES ($1, 'commentator', '2026-09-02', TRUE, 'agent/role-transition');

-- 3. Sync the denorm
UPDATE entities SET entity_type = 'commentator' WHERE entity_id = $1;
```

Adding a **concurrent** role (player picks up off-season commentary work) skips
steps 1 and 3 — just insert with `is_primary = FALSE` and an open `effective_to`.

---

## Querying the timeline

**Who held a role during a period?**

```sql
SELECT entity_id, role, metadata_json
FROM entity_roles
WHERE role = 'player'
  AND effective_from <= '2010-12-31'
  AND (effective_to IS NULL OR effective_to >= '2010-01-01');
```

**Current primary role for an entity** (cheap — uses the denorm):

```sql
SELECT entity_type FROM entities WHERE entity_id = $1;
```

**All current roles for an entity** (concurrent included):

```sql
SELECT role, metadata_json, is_primary
FROM entity_roles
WHERE entity_id = $1 AND effective_to IS NULL;
```

---

## Why not unify into a `person` entity type?

We considered collapsing `player`, `coach`, `commentator`, `journalist`,
`referee`, `advisor` into a single `person` entity_type with a `roles` JSONB
array. Rejected because:

- Existing code (`insights.py`, `rag.py`, `generate_kb.py`, multiple routers)
  filters on `entity_type = 'player'`. Folding into `person` requires touching
  all of them.
- The wiki routes (`/wiki/player/...`, `/wiki/advisor/...`) are public URLs —
  changing them is a breaking surface change.
- A single denormalised `entity_type` is genuinely useful for the 95% of cases
  where someone holds one role. The SCD table handles the 5%.

Keeping `entity_type` flat + a separate `entity_roles` table gives us the
temporal queries we need without disturbing the rest of the system.

---

## Convention for new SCD-2 child tables

`entity_roles` follows the same shape as
[`player_team_history`](../../packages/db/migrations/005_add_player_team_history.sql):
`effective_from` / `effective_to` / `is_primary` (or `is_current`) /
`metadata_json` / `source`. Future temporal tables (e.g. coach-club tenure,
commentator-network tenure) should follow the same shape.

When a third such table is added, revisit and consider unifying into a generic
`entity_affiliations` table. Two specialised tables is fine; three is the
trigger to consolidate.

---

## Channel ≠ Person

A common modelling mistake is to put a channel (SC Playbook YouTube) and the
person behind it (Tim Williams) on the same wiki page. We split them deliberately:

- **Channels** are operational outlets — they have URLs, platforms, polling
  cadence, and are tracked in the `channels` table. Channel wiki pages are
  seeded from this table on day one (47 of them as of `019_wiki_channels.sql`).
- **Advisors** (the person/voice) are entities with the `advisor` role. Advisor
  wiki pages describe the person, roll up calls across all the channels they
  publish through, and link out to those channels.

A channel can have many hosts (Seven Tackle Set has three); a person can publish
through many channels (Tim Williams via SC Playbook YouTube + Beers &
Breakevens). This is a many-to-many relationship — eventually modelled in a
`channel_hosts` table, deferred until advisor pages exist.

For now: channel pages render with a "Hosts will be linked once advisor pages
exist" placeholder. As speaker diarisation lands and the agent confidently
identifies named voices, advisor entities and pages get created, and the
channel ↔ advisor links populate.

---

## Related

- [Wiki overview](../pages/wiki/overview.md) — page types and routes
- [Wiki content pipeline](../pages/wiki/content-pipeline.md) — agent role-transition responsibilities + channel section conventions
- [Information architecture](../architecture/04-information-architecture.md) — full data model
- `packages/db/migrations/018_entity_roles.sql` — entity_roles schema
- `packages/db/migrations/019_wiki_channels.sql` — channel wiki pages
- `packages/db/migrations/005_add_player_team_history.sql` — sibling SCD-2 table
