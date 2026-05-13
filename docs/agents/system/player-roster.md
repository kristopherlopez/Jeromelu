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

The `teams` table is a precondition — baseline seed of all NRL/NRLW
clubs plus reserve grades lives in migration `039_seed_teams_2026.sql`
and applies to local and prod via the standard `make migrate` /
`migrate.sh` path. Incremental top-ups go through the admin endpoint
`POST /api/admin/teams/seed` (`make prod-seed-teams`). The roster module
looks up Team rows by slug; if any of the 17 NRL clubs are missing it
raises a clear precondition error rather than creating shadow rows.

---

## Endpoints

Five admin endpoints, all behind the same `X-Admin-Key` auth:

- `POST /api/admin/teams/seed`     — `services/api/app/routers/teams.py`
- `POST /api/admin/players/seed`   — `services/api/app/routers/players.py`
- `POST /api/admin/players/refresh` — `services/api/app/routers/players.py`
- `POST /api/admin/players/fetch-and-refresh` — `services/api/app/routers/players.py`
- `POST /api/admin/players/refresh-nrlcom` — `services/api/app/routers/players.py`

The team / seed / refresh endpoints reuse the same logic as their local
seed scripts — `seed_teams()` from `jeromelu_shared.teams`, and
`seed_roster()` / `refresh_roster()` from `jeromelu_shared.players.roster`.
The `/fetch-and-refresh` endpoint composes `fetch_supercoach_roster()`
(from `jeromelu_shared.players.supercoach`) with `refresh_roster()` so
prod can run the whole weekly job in a single no-payload call. The
`/refresh-nrlcom` endpoint walks the existing `people` rows and enriches
them from nrl.com profile pages (dob, image, height, weight,
birthplace) — see [nrl.com enrichment](#nrlcom-enrichment) below.

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
  "counts": {"nrl": 17, "nsw_cup": 12, "qld_cup": 5, "nrlw": 12}
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

### `POST /api/admin/players/fetch-and-refresh`

Server-side equivalent of `/refresh`: the API container fetches the SC
roster directly from `supercoach.com.au`'s unauthenticated `players-cf`
endpoint, validates the response covers all 17 NRL clubs and ≥400
players, then runs the same SCD-2 diff. **No body** — just the admin
key plus an optional `?season=YYYY` query param.

```bash
make prod-fetch-and-refresh-players ADMIN_KEY=$ADMIN_KEY
```

Response shape — same as `/refresh` plus a `fetched` count:
```json
{
  "ok": true,
  "fetched": 550,
  "counts": { "...": "as above" },
  "transitions": [ "..." ]
}
```

Errors:
- `502 Bad Gateway` — SC fetch failed validation (truncated payload,
  missing teams, non-list response). Refresh is NOT run; current state
  is untouched.
- `409 Conflict` — teams not seeded yet (`make prod-seed-teams` first).

This is the **preferred weekly path**. Cron-friendly because nothing
needs to be shipped between machines — wire one crontab line on the
Lightsail box and the refresh runs unattended.

### `POST /api/admin/players/refresh-nrlcom`

<a name="nrlcom-enrichment"></a>
**Enrichment, not enumeration.** Walks every player row that has a
current `player_attributes` row, derives a profile URL
(`https://www.nrl.com/players/nrl-premiership/{team_short}/{slug}/`),
fetches it, and parses the embedded `<script type="application/ld+json">`
JSON-LD block. Promotes:

| Field | Target | Update rule |
|---|---|---|
| `birthDate` | `people.dob` | Set if currently null (lifetime constant) |
| `image.url` | `people.image_url` | Always update (photos refresh seasonally) |
| `birthPlace.address` | `people.metadata_json.birthplace_text` | Set if empty (raw text — no normalisation in v1) |
| `height.value` (cm) | `player_attributes.height_cm` | In-place update on diff (re-measurements aren't SCD-2 transitions) |
| `weight.value` (kg) | `player_attributes.weight_kg` | In-place update on diff |

Ignored in v1: `jobTitle` (captaincy is per-match — see
`match_team_lists.is_captain`).

```bash
make prod-refresh-players-nrlcom ADMIN_KEY=$ADMIN_KEY
# Single-club test:
make prod-refresh-players-nrlcom ADMIN_KEY=$ADMIN_KEY TEAM=Broncos
# Throttled (if upstream rate-limits):
make prod-refresh-players-nrlcom ADMIN_KEY=$ADMIN_KEY RATE_LIMIT_MS=200
```

Sequential by design — ~80s for a full 17-club run, ~5s per club.

Empirical hit rate (2026-05 first run, no overrides): **85%** (469 / 550).
The remaining 15% break down as:
- Name shortenings nrl.com uses but SC doesn't (Thomas → Tom, Daniel → Dan)
- Recently-transferred players without a published profile yet
- Censored source data (SC has e.g. ``Jack *** Bird``)

All are addressable via per-person overrides; the override system is
designed for exactly this long tail.

#### Team URL slugs

`Team.short_name` maps to a per-club URL slug. Most clubs use the bare
nickname; two keep the full prefix. Encoded in
``NRLCOM_TEAM_OVERRIDES`` in ``nrlcom.py``:

| Team.short_name | nrl.com URL slug |
|---|---|
| Tigers | `wests-tigers` |
| Rabbitohs | `south-sydney-rabbitohs` |
| Sea Eagles | `sea-eagles` (default rule handles it) |
| All others | lowercase short_name (`broncos`, `sharks`, ...) |

If a future club rebrand changes the slug, update the override map.

#### Per-person overrides

Slug derivation (`lower(canonical_name).replace(' ', '-')`) misses ~5–10%
of names: apostrophes, accents, recently-traded players still on the
old club's nrl.com page, or nrl.com typos. Override on
`people.metadata_json.nrlcom`:

```json
{
  "slug":       "kontoni-staggs",   // alternative slug (nrl.com has a typo for Kotoni)
  "team_short": "raiders",          // alternative team_short (rare, e.g. mid-season trade)
  "skip":       true                // skip this player entirely (retired, won't have a profile)
}
```

Bookkeeping keys are written by the refresh itself and survive the
operator-supplied keys above:

| Key | Set when | Meaning |
|---|---|---|
| `last_checked` | every run | ISO date of the most recent attempt |
| `last_status` | every run | `"ok"`, `"404"`, or `"error"` |
| `tried_url` | every run | What URL was actually fetched |
| `last_error` | error path only | upstream HTTP error text; cleared on next OK |

#### Finding mismatches

```sql
SELECT canonical_name,
       metadata_json->'nrlcom'->>'tried_url' AS tried_url
FROM people
WHERE metadata_json->'nrlcom'->>'last_status' = '404'
ORDER BY canonical_name;
```

Set the override (`UPDATE people SET metadata_json = jsonb_set(...)`),
re-run the refresh, the row flips to `last_status = 'ok'`.

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

Weekly during season, Tuesdays after team-list announcements. Off-season:
monthly is plenty.

**Preferred (cron):**

```bash
make prod-fetch-and-refresh-players ADMIN_KEY=$ADMIN_KEY
```

The API container fetches the SC roster itself and runs the diff. Wire
this to crontab on the Lightsail box for unattended weekly runs — the
SC `players-cf` endpoint is unauthenticated, so no manual login is
needed. Suggested crontab line (Tuesday 09:00 AEST):

```
0 22 * * 1   ADMIN_KEY=... make -C /opt/jeromelu prod-fetch-and-refresh-players >> /var/log/jeromelu/refresh-players.log 2>&1
```
(Cron runs in UTC; 22:00 Mon UTC = 09:00 Tue AEST.)

**Manual / legacy paths:**

- `/scrape-supercoach` skill + `make prod-refresh-players ADMIN_KEY=...`
  — older pre-endpoint flow, still works when you want the YAML
  regenerated locally for transcript-cleaning. The skill itself runs an
  interactive Playwright + Google OAuth flow; the modern unauthenticated
  fetcher (`scripts/data/fetchers/fetch_supercoach_players.py`) is a
  drop-in replacement that doesn't need it.
- `make fetch-players` — local-dev helper that fetches the JSON and
  regenerates `data/players.yaml` (used by transcript cleaning). No
  production side-effects.

A daily diff job that polls `nrl.com/news` for transfer announcements
between weekly refreshes is a v2 candidate — see [v2 expansion](#sources-today-vs-tomorrow)
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
- `packages/shared/jeromelu_shared/players/supercoach.py` — SC fetcher
- `packages/shared/jeromelu_shared/players/nrlcom.py` — nrl.com profile fetcher
- `packages/shared/jeromelu_shared/players/nrlcom_refresh.py` — enrichment loop
- `scripts/data/fetchers/fetch_supercoach_players.py` — local CLI fetch
- `services/api/app/routers/players.py` — admin endpoints
- `.claude/skills/scrape-supercoach/skill.md` — legacy local-only scraper
