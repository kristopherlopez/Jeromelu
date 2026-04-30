---
tags: [area/agents, subarea/system, status/live]
---

# Player Roster

How player identity, club affiliation, and slow-changing player facts get
into the database — and stay current as the season unfolds.

Status: **Live** (migration 027).

---

## The three temporal regimes

Player facts split by how often they change. Don't conflate them.

| Regime | Examples | Storage |
|---|---|---|
| **Lifetime constants** | dob, birth country, debut date, full name | `entities.metadata_json` |
| **Slowly changing (SCD-2)** | team, primary position, height, weight, contract | `player_attributes` |
| **Per-round (fast)** | SC price, breakeven, score, minutes, jersey, grade | `player_rounds` |

Cross-entity-type role tenure (player → coach → commentator) lives in
`entity_roles`. See [entity-roles](../../concepts/entity-roles.md).

`grade` is per-round, not slow-changing — a player getting demoted to NSW
Cup mid-season and promoted back the following week shouldn't open and
close `player_attributes` rows. `player_attributes.team_id` always points
to the **parent NRL/NRLW team** the player is contracted to; what grade
they actually played in for round R is captured in `player_rounds`.

---

## Pipeline

```
SuperCoach players-cf API   ──▶ scripts/data/scraped_players_api_raw.json
                                          │
                              ┌───────────┴───────────┐
                              ▼                       ▼
              local: make seed-players       prod: make prod-seed-players
                              │                       │
                              ▼                       ▼
                  jeromelu_shared.players.roster.seed_roster
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
          entities      entity_roles    player_attributes
                            (player)        (current row,
                                             team_id → teams)
```

The `teams` table is a precondition — populated locally by
`scripts/data/seed_teams.py` (`make seed-teams`) from `data/teams.yaml`,
and in prod via the parallel admin endpoint `POST /api/admin/teams/seed`
(`make prod-seed-teams`) which takes the same yaml content as JSON. The
roster module looks up Team rows by slug; if any of the 17 NRL clubs are
missing it raises a clear precondition error rather than creating shadow
rows.

---

## Endpoints

Three admin endpoints, all behind the same `X-Admin-Key` auth:

- `POST /api/admin/teams/seed`     — `services/api/app/routers/teams.py`
- `POST /api/admin/players/seed`   — `services/api/app/routers/players.py`
- `POST /api/admin/players/refresh` — `services/api/app/routers/players.py`

The team and player endpoints reuse the same logic as their local seed
scripts — `seed_teams()` from `jeromelu_shared.teams`, and
`seed_roster()` / `refresh_roster()` from `jeromelu_shared.players.roster`.

### `POST /api/admin/teams/seed`

Idempotent first-run / re-seed of the `teams` table. Body is the parsed
contents of `data/teams.yaml` (top-level `teams` map plus optional `nrlw`
map). Re-running only bumps `updated_at` on existing rows.

```bash
make prod-seed-teams ADMIN_KEY=$ADMIN_KEY
```

Response shape:
```json
{
  "ok": true,
  "counts": {"nrl": 17, "nsw_cup": 12, "qld_cup": 5, "nrlw": 12, "entities_linked_this_run": 0}
}
```

### `POST /api/admin/players/seed`

First-run idempotent seed. Body is the SC roster JSON array. Existing
current `player_attributes` rows are left alone — re-running this
endpoint is safe and won't churn data.

```bash
make prod-seed-players ADMIN_KEY=$ADMIN_KEY
```

Response shape:
```json
{
  "ok": true,
  "players_seen": 521,
  "entities_created": 521,
  "attributes_inserted": 521,
  "attributes_noop": 0,
  "skipped_unknown_team": 0
}
```

### `POST /api/admin/players/refresh`

Diff a fresh roster against current state, apply SCD-2 transitions for
team / primary-position changes, add rows for never-before-seen players.

```bash
make prod-refresh-players ADMIN_KEY=$ADMIN_KEY
```

Response shape:
```json
{
  "ok": true,
  "counts": {
    "players_seen": 521,
    "new_players": 2,
    "team_changes": 1,
    "position_changes": 0,
    "unchanged": 518,
    "skipped_unknown_team": 0
  },
  "transitions": [
    {"kind": "team_change",  "name": "Player X", "from_team_slug": "...", "to_team_slug": "..."},
    {"kind": "new_player",   "name": "Player Y", "team_slug": "..."}
  ]
}
```

The transitions list is the input the feed/wiki layer uses to surface
"Brisbane added Player Y, dropped Player X" cards.

---

## SCD-2 transition pattern

Same as the role transition in
[entity-roles](../../concepts/entity-roles.md#role-transition-pattern).
Wrapped in a transaction inside `refresh_roster()`:

```sql
-- 1. Close the current row
UPDATE player_attributes
   SET effective_to = CURRENT_DATE, is_current = FALSE, updated_at = now()
 WHERE entity_id = $1 AND is_current;

-- 2. Open the new current row
INSERT INTO player_attributes (
    entity_id, team_id, primary_position, metadata_json,
    effective_from, is_current, source
) VALUES ($1, $2, $3, $4, CURRENT_DATE, TRUE, 'supercoach');
```

The partial unique index `uq_player_attributes_current` enforces that
exactly one row per entity is current — if step 1 is skipped, step 2 will
fail rather than silently create a duplicate.

---

## Cadence

Weekly during season. Trigger by hand on Tuesdays after team-list
announcements:

1. Run `/scrape-supercoach` locally (interactive 2FA blocks unattended
   automation).
2. `make prod-refresh-players ADMIN_KEY=$ADMIN_KEY` posts the JSON.

Off-season: monthly is plenty.

A daily diff job that polls `nrl.com/news` for transfer announcements
between weekly refreshes is a v2 candidate — see [v2 expansion](#v2-multi-source-rosters)
below.

---

## Sources today vs. tomorrow

**v1 (now):** SuperCoach is the single source. All `player_attributes`
rows have `source='supercoach'`. SC only knows the top-grade NRL roster
(521 players), so development players in NSW Cup / Q Cup are not
represented yet.

**v2 (planned):**
- `nrl.com` — top-grade roster, becomes canonical for `grade='nrl'`.
- `nswrl.com.au` — NSW Cup roster.
- `qrl.com.au` — Queensland Cup roster.
- SC drops to an overlay layer (just SC id + SC positions) on top of
  NRL.com truth.
- Development players who only exist in feeder grades get
  `player_attributes` rows that point to feeder Team rows in `teams`.
- Per-round grade (NRL vs NSW Cup vs Q Cup) decision needed in
  `player_rounds` — either add `competition` / `grade` columns, or split
  into `player_rounds_nrl` + a sibling Cup table.

---

## Related

- [Data catalogue: player_attributes](../../operations/data-catalogue.md#player_attributes)
- [Entity roles SCD-2 pattern](../../concepts/entity-roles.md)
- `packages/db/migrations/027_consolidate_player_scd.sql` — schema
- `packages/db/migrations/026_teams.sql` — teams table this FKs into
- `packages/shared/jeromelu_shared/players/roster.py` — seed + refresh
- `services/api/app/routers/players.py` — admin endpoints
- `.claude/skills/scrape-supercoach/skill.md` — how to produce the SC roster JSON
