---
tags: [area/operations, status/executed]
---

# Refactor: drop `entities`, move to typed tables + association junctions

**Status: executed.** Migrations 036, 037 (CHECK constraint cleanup), and 038 are applied. Application code has been switched over to typed FKs / association junctions. The data catalogue has been updated to match. Kept in-tree for historical reference; archive when the events / squad rebuilds happen and the "deferred" notes lose relevance.

## Goal

Replace the polymorphic `entities` identity hub with **typed per-type tables** and **typed association junctions**. Outcomes:

1. Direct, type-enforced FKs everywhere outside the polymorphic boundaries.
2. No bookkeeping `teams.entity_id` / `venues.entity_id` / `matches.entity_id` redundancy.
3. Cross-type subjects modeled as **first-class many-to-many** via association tables — a claim or prediction can name a player + team + match all at once, with `role` distinguishing them.
4. Junction tables use **typed nullable FKs + CHECK exactly-one** (Option B), preserving DB-level referential integrity.
5. metadata_json kept as **lean long-tail JSON** only; universal/queryable fields promoted to typed columns on every typed entity.

## Architectural insight worth surfacing

| Entity | Needs SCD-2 attributes table? |
|---|---|
| **people** | **Yes** — `people_attributes` (team, position, height, weight, contract change often) |
| teams | No (typed columns + no history) |
| venues | No |
| matches | No (per-event facts captured in `events`) |
| rounds | No |
| channels | No |

Only humans accumulate fast-changing biographical facts. Everything else either has stable facts (typed columns suffice) or per-event facts captured elsewhere (`player_rounds`, `match_team_lists`, `injuries`). One SCD-2 history table in the whole schema, not five.

---

## Target schema

### New tables — identity layer

#### `people`

Unified table for every human actor — players, coaches, advisors, commentators, journalists, referees. Lifetime-stable facts get typed columns; long-tail goes in `metadata_json`.

```sql
CREATE TABLE people (
    person_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name TEXT NOT NULL,
    aliases        TEXT[] NOT NULL DEFAULT '{}',
    slug           TEXT UNIQUE,

    -- Stable, queryable, universal-ish lifetime facts
    dob            DATE,
    country        TEXT,                          -- 'AU', 'NZ', 'UK', 'PNG', ...
    image_url      TEXT,

    -- Cross-system identifier (stable per person, used for joins/imports)
    supercoach_id  INTEGER UNIQUE,                -- NULL for non-players

    -- Long-tail / sparse / unstructured. Refactor any heavily-used key into a column when justified.
    metadata_json  JSONB NOT NULL DEFAULT '{}',

    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_people_name ON people (canonical_name);
CREATE INDEX idx_people_country ON people (country) WHERE country IS NOT NULL;
```

#### `people_attributes`

SCD-2 of slow-changing per-person facts. Replaces today's `player_attributes` but extended to cover non-player roles where applicable. Closed-and-reopened on change.

```sql
CREATE TABLE people_attributes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id           UUID NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
    team_id             UUID REFERENCES teams(team_id) ON DELETE SET NULL,
    primary_position    TEXT,                     -- SC position string (FRF/HOK/HFB/...)
    height_cm           INTEGER,
    weight_kg           INTEGER,
    contract_until      DATE,
    real_salary_aud     INTEGER,                  -- reserved for future feed
    metadata_json       JSONB NOT NULL DEFAULT '{}',  -- secondary_positions etc. (long-tail; promote to columns later if heavily queried)

    effective_from      DATE NOT NULL,
    effective_to        DATE,
    is_current          BOOLEAN NOT NULL DEFAULT TRUE,
    source              TEXT NOT NULL DEFAULT 'seed',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE INDEX idx_people_attributes_person_current ON people_attributes (person_id, is_current);
CREATE INDEX idx_people_attributes_team_current   ON people_attributes (team_id, is_current);
CREATE UNIQUE INDEX uq_people_attributes_current
    ON people_attributes (person_id) WHERE is_current;
```

#### `people_roles` (renamed from `entity_roles`)

SCD-2 of role tenure. Multi-valued at a single point in time (Adam Reynolds = active player + occasional commentator). Same shape as today, just `person_id` FK.

```sql
CREATE TABLE people_roles (
    role_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id      UUID NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
    role           TEXT NOT NULL,                 -- 'player'|'coach'|'commentator'|'journalist'|'referee'|'advisor'
    effective_from DATE NOT NULL,
    effective_to   DATE,
    is_primary     BOOLEAN NOT NULL DEFAULT FALSE,
    metadata_json  JSONB NOT NULL DEFAULT '{}',
    source         TEXT NOT NULL DEFAULT 'seed',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    CHECK (role IN ('player','coach','commentator','journalist','referee','advisor')),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE INDEX idx_people_roles_person       ON people_roles (person_id, effective_to);
CREATE INDEX idx_people_roles_role_period  ON people_roles (role, effective_from, effective_to);
CREATE UNIQUE INDEX uq_people_roles_primary_current
    ON people_roles (person_id) WHERE is_primary AND effective_to IS NULL;
```

No `entity_type` denorm on `people` — coverage is provided by `people_roles`. Queries that need "current commentators" JOIN to `people_roles WHERE role='commentator' AND is_primary AND effective_to IS NULL`.

#### `rounds`

Currently `round` is just an `entity_type` with no real backing table. This refactor gives it one with promoted typed columns.

```sql
CREATE TABLE rounds (
    round_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    season             INTEGER NOT NULL,
    round_number       INTEGER,                   -- NULL for finals (use round_label)
    round_label        TEXT NOT NULL,             -- 'Round 5', 'Finals Week 1', 'Magic Round'
    starts_at          TIMESTAMPTZ,
    ends_at            TIMESTAMPTZ,

    -- Promoted from would-be metadata_json:
    is_magic_round     BOOLEAN NOT NULL DEFAULT FALSE,
    is_rep_weekend     BOOLEAN NOT NULL DEFAULT FALSE,
    is_finals          BOOLEAN NOT NULL DEFAULT FALSE,

    metadata_json      JSONB NOT NULL DEFAULT '{}',

    UNIQUE (season, round_number)
);

CREATE INDEX idx_rounds_season ON rounds (season);
```

### New tables — opinion / output association junctions

For tables where the row is fundamentally *about* multiple typed entities at once (a claim or prediction can name a player + team + match in one go), the subject relationship becomes many-to-many via a junction. **Option B** shape: typed nullable FKs + CHECK exactly-one.

#### `claim_associations`

```sql
CREATE TABLE claim_associations (
    association_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id       UUID NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    role           TEXT NOT NULL,                 -- 'subject'|'context'|'opponent'|'mentioned'
    person_id      UUID REFERENCES people(person_id)   ON DELETE CASCADE,
    team_id        UUID REFERENCES teams(team_id)      ON DELETE CASCADE,
    match_id       UUID REFERENCES matches(match_id)   ON DELETE CASCADE,
    venue_id       UUID REFERENCES venues(venue_id)    ON DELETE CASCADE,
    round_id       UUID REFERENCES rounds(round_id)    ON DELETE CASCADE,

    CHECK (
        (person_id IS NOT NULL)::int +
        (team_id   IS NOT NULL)::int +
        (match_id  IS NOT NULL)::int +
        (venue_id  IS NOT NULL)::int +
        (round_id  IS NOT NULL)::int = 1
    ),

    UNIQUE NULLS NOT DISTINCT (claim_id, role, person_id, team_id, match_id, venue_id, round_id)
);

CREATE INDEX idx_claim_associations_claim   ON claim_associations (claim_id);
CREATE INDEX idx_claim_associations_person  ON claim_associations (person_id) WHERE person_id IS NOT NULL;
CREATE INDEX idx_claim_associations_team    ON claim_associations (team_id)   WHERE team_id   IS NOT NULL;
CREATE INDEX idx_claim_associations_match   ON claim_associations (match_id)  WHERE match_id  IS NOT NULL;
CREATE INDEX idx_claim_associations_venue   ON claim_associations (venue_id)  WHERE venue_id  IS NOT NULL;
CREATE INDEX idx_claim_associations_round   ON claim_associations (round_id)  WHERE round_id  IS NOT NULL;
```

`UNIQUE NULLS NOT DISTINCT` requires Postgres 15+. If older, use a coalesce-style functional unique index instead.

#### `prediction_associations`

```sql
CREATE TABLE prediction_associations (
    association_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id   UUID NOT NULL REFERENCES predictions(prediction_id) ON DELETE CASCADE,
    role            TEXT NOT NULL,                -- 'subject'|'context'|'opponent'|'mentioned'
    person_id       UUID REFERENCES people(person_id)  ON DELETE CASCADE,
    team_id         UUID REFERENCES teams(team_id)     ON DELETE CASCADE,
    match_id        UUID REFERENCES matches(match_id)  ON DELETE CASCADE,
    venue_id        UUID REFERENCES venues(venue_id)   ON DELETE CASCADE,
    round_id        UUID REFERENCES rounds(round_id)   ON DELETE CASCADE,

    CHECK (
        (person_id IS NOT NULL)::int +
        (team_id   IS NOT NULL)::int +
        (match_id  IS NOT NULL)::int +
        (venue_id  IS NOT NULL)::int +
        (round_id  IS NOT NULL)::int = 1
    ),

    UNIQUE NULLS NOT DISTINCT (prediction_id, role, person_id, team_id, match_id, venue_id, round_id)
);
-- + the same set of partial indexes per FK as claim_associations.
```

#### `decision_associations`

Identical shape to `prediction_associations`, with `decision_id UUID NOT NULL REFERENCES decisions(decision_id) ON DELETE CASCADE`. Roles include `'subject'|'player_in'|'player_out'|'context'`.

#### `event_associations` — **deferred** (events table outside refactor scope)

The existing `events.related_entity_ids[]` array is left as-is by this refactor. The `events` table will be redesigned in a separate piece of work; converting the array to a junction now would couple two refactors. After Phase 3 lands and `entities` is dropped, the UUIDs in `events.related_entity_ids[]` become dangling references — accepted until events is rebuilt.

#### `remark_associations` (planned, when `remarks` lands)

Same shape as `claim_associations` with `remark_id` FK. Build alongside `remarks` itself when that work happens — not part of this refactor.

### Modified tables — column promotions on existing typed entities

The same "metadata_json is small-scale EAV" discipline applies everywhere. Promote universal/queryable fields to typed columns on each typed entity.

#### `teams` — promote from metadata_json

```sql
ALTER TABLE teams
    ADD COLUMN primary_colour    TEXT,
    ADD COLUMN secondary_colour  TEXT,
    ADD COLUMN founded_year      INTEGER,
    ADD COLUMN home_venue_id     UUID REFERENCES venues(venue_id) ON DELETE SET NULL,
    ADD COLUMN logo_url          TEXT;
-- backfill from existing teams.metadata_json keys if present
```
metadata_json keeps long-tail (nicknames, fan_club_url, naming_history, etc.).

#### `venues` — promote from metadata_json

```sql
ALTER TABLE venues
    ADD COLUMN latitude     NUMERIC(9, 6),
    ADD COLUMN longitude    NUMERIC(9, 6),
    ADD COLUMN opened_year  INTEGER,
    ADD COLUMN image_url    TEXT;
```
metadata_json keeps long-tail (transport_links, parking_capacity, naming_history).

#### `matches` — promote from metadata_json

```sql
ALTER TABLE matches
    ADD COLUMN is_magic_round  BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN is_rep_weekend  BOOLEAN NOT NULL DEFAULT FALSE;
```
metadata_json keeps long-tail (ladder snapshots, broadcast quirks, score corrections).

#### `matches` — accommodate bye rows

Byes live in `matches` rather than a separate junction. A bye is a `matches` row with `home_team_id` set to the team on bye, `away_team_id` NULL, `status='bye'`. `home_team_id` is semantically overloaded for bye rows (it's just *the* team, not "home") — accepted overload to avoid renaming columns across the whole codebase.

```sql
-- away_team_id becomes nullable
ALTER TABLE matches ALTER COLUMN away_team_id DROP NOT NULL;

-- 'bye' added to status enum
ALTER TABLE matches
    DROP CONSTRAINT ck_matches_status,
    ADD CONSTRAINT ck_matches_status CHECK (status IN
        ('scheduled','live','final','postponed','cancelled','forfeit','bye'));

-- bye rows have no opponent; non-bye rows must have one
ALTER TABLE matches
    ADD CONSTRAINT ck_matches_bye_no_opponent CHECK (
        (status='bye' AND away_team_id IS NULL)
        OR (status<>'bye' AND away_team_id IS NOT NULL)
    );

-- existing home_team_id ≠ away_team_id stays correct
-- (NULL ≠ X is NULL → CHECK passes for byes, which is what we want)
-- existing score-paired CHECK stays correct (both NULL on byes is fine)
```

For a bye row: `home_team_id` = team on bye, `away_team_id` = NULL, `status='bye'`, `kickoff_at`/`venue_id`/scores/weather/broadcast all NULL, `season`+`round` filled.

Existing match queries that don't care about byes filter `WHERE status<>'bye'` or `WHERE away_team_id IS NOT NULL`.

#### `channels` — already lean, no promotions needed.

#### `miner_candidates` — leave as-is.

Working table for the agent. metadata_json is intentionally heavy because it captures discovery-time platform-specific JSON (subs/views/duration from YouTube). Promoting would tightly couple to the response shape; flexibility is right for an agent inbox.

### Modified tables — drop redundant `entity_id` columns

Phase-3 destructive — listed here for completeness.

| Table | Drop |
|---|---|
| `teams` | `entity_id` |
| `venues` | `entity_id` |
| `matches` | `entity_id` |
| `player_attributes` | the whole table is replaced by `people_attributes` (renamed + person_id) |

### Modified tables — replace polymorphic single-subject FKs with typed-nullable + CHECK

These tables today have ONE `subject_entity_id` pointing at any kind. Under the refactor they get N typed nullable FKs + a CHECK that exactly one is populated.

| Table | Replaces | New columns |
|---|---|---|
| `wiki_pages` | `entity_id` | `person_id`, `team_id`, `match_id`, `venue_id`, `round_id`, `channel_id` (already there) — CHECK exactly-one |
| `consensus_snapshots` | `subject_entity_id` | `person_id`, `team_id`, `match_id`, `venue_id`, `round_id` — CHECK exactly-one |
| `knowledge_base` | `subject_entity_id` | same |

### Modified tables — replace polymorphic FK with direct typed FK (where the subject is always one kind)

| Table | Replaces | New column | Reason |
|---|---|---|---|
| `quotes` | `speaker_entity_id` | `speaker_person_id` FK → people | speaker is always a person |
| `predictions` | `predictor_entity_id` | `predictor_person_id` FK → people | predictor is always a person |
| `source_speakers` | `speaker_entity_id` | `speaker_person_id` FK → people | same |
| `match_team_lists` | `player_entity_id` | `player_id` FK → people | always a player-role person |
| `injuries` | `player_entity_id` | `player_id` FK → people | same |
| `claims` | `subject_entity_id` | (none — replaced by `claim_associations`) | already covered |
| `decisions` | `subject_entity_id` | (none — replaced by `decision_associations`) | already covered |

### Tables removed (Phase 1 / Phase 3)

- `source_annotations` — **dropped in Phase 1** (the table is empty post mig 034). Functionality absorbed into a generalised `claims` table — see "claims becomes the single extraction table" below.
- `entities` — gone after the refactor (Phase 3)
- `entity_roles` — replaced by `people_roles` (Phase 3)
- `player_attributes` — replaced by `people_attributes` (Phase 3)

### `claims` becomes the single extraction table

`source_annotations` and `claims` were doing the same conceptual job (extracted from a source span, attached to a subject, carrying type + sentiment). Genuine non-claim annotations (themes, mentions, sub-topic spans) are just claims with looser typing. Collapse into one table:

```sql
-- Phase 1: expand the kind enum (or drop the CHECK and validate in app)
ALTER TABLE claims
    DROP CONSTRAINT ck_claim_type,
    ADD CONSTRAINT ck_claim_type CHECK (claim_type IN (
        -- Fantasy-actionable (existing)
        'buy', 'sell', 'hold', 'captain', 'avoid', 'breakout', 'matchup_edge',
        -- Annotation-flavoured (new)
        'mention', 'theme', 'subtopic', 'sentiment', 'tactical_tag', 'highlight'
    ));

-- Phase 1: payload_json absorbs source_annotations.payload_json semantics
ALTER TABLE claims
    ADD COLUMN payload_json JSONB NOT NULL DEFAULT '{}';
```

The fantasy-claim use case becomes `WHERE claim_type IN ('buy','sell','hold','captain','avoid','breakout','matchup_edge')`. The Ledger filters by that. The agent's "everything Cleary was discussed about in this video" becomes one query through `claim_associations`.

Existing nullability already accommodates the broader use cases (`subject_entity_id` nullable for themes; `polarity`/`strength`/`effective_round`/`season` nullable for non-fantasy kinds; `claim_text` nullable; `quote_id` nullable).

The table keeps its `claims` name — renaming to `extractions` or similar is a wider sweep with little upside.

---

## Migration plan (3 phases)

### Phase 1 — Additive (migration 036)

All changes are additive. The old schema continues to work. New tables and columns coexist alongside.

```sql
-- 036a: new identity-layer tables
CREATE TABLE people (...);            -- DDL above
CREATE TABLE people_attributes (...); -- DDL above
CREATE TABLE people_roles (...);      -- DDL above
CREATE TABLE rounds (...);            -- DDL above

-- 036b: backfill people from entities, with metadata_json field promotion
INSERT INTO people (
    person_id, canonical_name, aliases, slug,
    dob, country, image_url, supercoach_id,
    metadata_json, created_at
)
SELECT
    entity_id, canonical_name, aliases, slug,
    (metadata_json->>'dob')::date,
    metadata_json->>'country',
    metadata_json->>'image_url',
    (metadata_json->>'supercoach_id')::int,
    -- strip the promoted keys from metadata_json
    metadata_json - 'dob' - 'country' - 'image_url' - 'supercoach_id',
    created_at
FROM entities
WHERE entity_type IN ('player','coach','referee','commentator','journalist','advisor');

-- 036c: backfill people_attributes from existing player_attributes
INSERT INTO people_attributes (
    id, person_id, team_id, primary_position, height_cm, weight_kg,
    contract_until, real_salary_aud, metadata_json,
    effective_from, effective_to, is_current, source, created_at, updated_at
)
SELECT
    id, entity_id, team_id, primary_position, height_cm, weight_kg,
    contract_until, real_salary_aud, metadata_json,
    effective_from, effective_to, is_current, source, created_at, updated_at
FROM player_attributes;

-- 036d: backfill people_roles from entity_roles
INSERT INTO people_roles (
    role_id, person_id, role, effective_from, effective_to, is_primary,
    metadata_json, source, created_at, updated_at
)
SELECT
    entity_role_id, entity_id, role, effective_from, effective_to, is_primary,
    metadata_json, source, created_at, updated_at
FROM entity_roles;

-- 036e: backfill rounds from entities (low row count; manual mapping)
INSERT INTO rounds (round_id, season, round_number, round_label, ...)
SELECT
    entity_id,
    (metadata_json->>'season')::int,
    (metadata_json->>'round_number')::int,
    canonical_name,
    ...
FROM entities WHERE entity_type='round';

-- 036f: column promotions on teams, venues, matches, rounds
ALTER TABLE teams ADD COLUMN primary_colour TEXT, ADD COLUMN secondary_colour TEXT,
    ADD COLUMN founded_year INTEGER, ADD COLUMN home_venue_id UUID REFERENCES venues(venue_id) ON DELETE SET NULL,
    ADD COLUMN logo_url TEXT;
-- + UPDATE teams SET ... = metadata_json->>'...' for any keys present
-- + UPDATE teams SET metadata_json = metadata_json - 'primary_colour' - ... (strip promoted keys)

ALTER TABLE venues ADD COLUMN latitude NUMERIC(9,6), ADD COLUMN longitude NUMERIC(9,6),
    ADD COLUMN opened_year INTEGER, ADD COLUMN image_url TEXT;
-- + same backfill+strip pattern

ALTER TABLE matches ADD COLUMN is_magic_round BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN is_rep_weekend BOOLEAN NOT NULL DEFAULT FALSE;
-- + same backfill+strip pattern

-- 036f-bis: matches accommodates bye rows
ALTER TABLE matches ALTER COLUMN away_team_id DROP NOT NULL;
ALTER TABLE matches
    DROP CONSTRAINT ck_matches_status,
    ADD CONSTRAINT ck_matches_status CHECK (status IN
        ('scheduled','live','final','postponed','cancelled','forfeit','bye'));
ALTER TABLE matches
    ADD CONSTRAINT ck_matches_bye_no_opponent CHECK (
        (status='bye' AND away_team_id IS NULL)
        OR (status<>'bye' AND away_team_id IS NOT NULL)
    );
-- backfill: byes are populated by the NRL.com fixture sync going forward
-- (or one-shot import from any historical bye list in the metadata_json of entities[entity_type='round']).

-- 036g: add typed FK columns alongside existing entity_id columns (nullable)
ALTER TABLE quotes               ADD COLUMN speaker_person_id  UUID REFERENCES people(person_id);
ALTER TABLE predictions          ADD COLUMN predictor_person_id UUID REFERENCES people(person_id);
ALTER TABLE source_speakers      ADD COLUMN speaker_person_id  UUID REFERENCES people(person_id);
ALTER TABLE match_team_lists     ADD COLUMN player_id          UUID REFERENCES people(person_id);
ALTER TABLE injuries             ADD COLUMN player_id          UUID REFERENCES people(person_id);
-- backfill each: SET *_person_id = entity_id (since people.person_id == entities.entity_id by design)

-- 036g-bis: is_captain captured per-match-per-team-per-player, not per-person
ALTER TABLE match_team_lists ADD COLUMN is_captain BOOLEAN NOT NULL DEFAULT FALSE;
-- backfill from player_attributes.metadata_json->>'is_captain' if applicable
-- (best-effort; future named-17 announcements set this from NRL.com data)

-- 036h: add typed nullable FKs + CHECK to single-subject polymorphic tables
ALTER TABLE wiki_pages
    ADD COLUMN person_id UUID REFERENCES people(person_id),
    ADD COLUMN team_id   UUID REFERENCES teams(team_id),
    ADD COLUMN match_id  UUID REFERENCES matches(match_id),
    ADD COLUMN venue_id  UUID REFERENCES venues(venue_id),
    ADD COLUMN round_id  UUID REFERENCES rounds(round_id);
-- backfill from entity_id, dispatching by entities.entity_type
-- NOTE: ck_wiki_subject CHECK gets adjusted in phase 3

-- same column-add + backfill for consensus_snapshots, knowledge_base.

-- 036i: drop source_annotations (empty post mig 034); generalise claims
DROP TABLE source_annotations;

ALTER TABLE claims
    DROP CONSTRAINT ck_claim_type,
    ADD CONSTRAINT ck_claim_type CHECK (claim_type IN (
        'buy','sell','hold','captain','avoid','breakout','matchup_edge',
        'mention','theme','subtopic','sentiment','tactical_tag','highlight'
    )),
    ADD COLUMN payload_json JSONB NOT NULL DEFAULT '{}';

-- 036j: create junction tables, backfill from existing single subject_entity_id
CREATE TABLE claim_associations (...);       -- DDL above
CREATE TABLE prediction_associations (...);  -- same shape
CREATE TABLE decision_associations (...);    -- same shape
-- (event_associations omitted — events table is out of scope for this refactor)

-- backfill claim_associations from claims.subject_entity_id
-- (one row per claim, role='subject', dispatched into the right typed FK by entity_type)
INSERT INTO claim_associations (claim_id, role, person_id, team_id, match_id, venue_id, round_id)
SELECT
    c.claim_id, 'subject',
    CASE WHEN e.entity_type IN ('player','coach','referee','commentator','journalist','advisor') THEN e.entity_id END,
    t.team_id,                      -- via teams.entity_id = e.entity_id when entity_type='team'
    NULL, NULL, NULL                -- match/venue/round dispatched similarly via their entity_id columns
FROM claims c
JOIN entities e ON c.subject_entity_id = e.entity_id
LEFT JOIN teams t ON e.entity_type='team' AND t.entity_id = e.entity_id;
-- (similar dispatch logic for matches, venues, rounds)

-- same backfill for prediction_associations, decision_associations.
-- (events.related_entity_ids[] left as-is; events refactor is a separate future piece of work)
```

**Outcome of phase 1:** Every typed FK and association is populated. Old `entity_id` columns still present and usable. Application code still works against the old schema.

### Phase 2 — Code switchover (no SQL)

Update API code in this order:

1. **ORM models** (`packages/shared/jeromelu_shared/db/models.py`)
   - Add new model classes: `Person`, `PersonAttributes`, `PersonRole`, `Round`, `RoundBye`, `ClaimAssociation`, `PredictionAssociation`, `DecisionAssociation`, `EventAssociation`
   - Add new typed FK fields to existing models (alongside old `entity_id` fields)
   - Don't drop the old fields yet — both work during transition

2. **Read paths** — switch from `entity_id` to typed FK / junction queries:
   - `services/api/app/routers/` — every router that filters on entity_id
   - Wiki: `wiki_pages.entity_id` → 6 typed FKs + dispatch on which is set
   - Claim retrieval: `claims.subject_entity_id` → JOIN through `claim_associations`
   - Same for predictions, decisions, knowledge_base, consensus_snapshots
   - Events: untouched in this refactor (rebuilt later)

3. **Write paths** — every INSERT/UPDATE that touches polymorphic FKs:
   - Claim extraction: write to `claim_associations` instead of `claims.subject_entity_id`
   - Wiki creation: dispatch on subject kind, write to the right typed FK
   - Same for everything else

4. **Tests** — full suite green against the new shape.

**Estimate:** 1–2 days of focused work. Many files. The grep for `entity_id` and `subject_entity_id` is the to-do list.

### Phase 3 — Destructive (migration 037)

Once phase 2 is committed and tests pass:

```sql
-- 037-pre: verification — assert every old-FK row has a corresponding new-FK row populated.
-- If any of these counts is non-zero, abort the migration.
DO $$
DECLARE drift INT;
BEGIN
    SELECT COUNT(*) INTO drift FROM claims c
        WHERE c.subject_entity_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM claim_associations ca WHERE ca.claim_id = c.claim_id);
    IF drift > 0 THEN RAISE EXCEPTION 'claims drift: % unmigrated rows', drift; END IF;
    -- repeat for each table being dropped
END $$;

-- 037a: drop old polymorphic FKs from output tables
ALTER TABLE claims              DROP COLUMN subject_entity_id;
ALTER TABLE predictions         DROP COLUMN subject_entity_id, DROP COLUMN predictor_entity_id;
ALTER TABLE decisions           DROP COLUMN subject_entity_id;
ALTER TABLE consensus_snapshots DROP COLUMN subject_entity_id;
ALTER TABLE knowledge_base      DROP COLUMN subject_entity_id;
ALTER TABLE wiki_pages          DROP COLUMN entity_id;
ALTER TABLE quotes              DROP COLUMN speaker_entity_id;
ALTER TABLE source_speakers     DROP COLUMN speaker_entity_id;
ALTER TABLE match_team_lists    DROP COLUMN player_entity_id;
ALTER TABLE injuries            DROP COLUMN player_entity_id;
-- events table left untouched (refactor scope excludes events; rebuilt later)

-- 037b: drop redundant entity_id from typed tables
ALTER TABLE teams    DROP COLUMN entity_id;
ALTER TABLE venues   DROP COLUMN entity_id;
ALTER TABLE matches  DROP COLUMN entity_id;

-- 037c: drop the old identity tables
DROP TABLE player_attributes;
DROP TABLE entity_roles;
DROP TABLE entities;

-- 037d: tighten CHECK constraints on the single-subject polymorphic tables
ALTER TABLE wiki_pages
    DROP CONSTRAINT ck_wiki_page_subject,
    ADD CONSTRAINT ck_wiki_page_subject CHECK (
        (person_id IS NOT NULL)::int + (team_id IS NOT NULL)::int +
        (match_id  IS NOT NULL)::int + (venue_id IS NOT NULL)::int +
        (round_id  IS NOT NULL)::int + (channel_id IS NOT NULL)::int = 1
    );
-- same for consensus_snapshots, knowledge_base.
```

---

## Code change scope

Everywhere `entity_id` or `subject_entity_id` appears in `services/api/app/`. Initial grep hot spots:

- `app/routers/` — claims, predictions, decisions, wiki, kb endpoints
- `app/miner/` — entity references in dedupe and persistence logic
- Any ingestion scripts in `services/workers/` or `scripts/`
- `app/wiki/` — channel/entity wiki dispatch
- Knowledge base RAG retrieval

Plus the ORM models and `db/__init__.py` exports.

---

## Documentation Updates

Once executed:

- **`docs/operations/data-catalogue/`** — biggest update. Identity layer now lives in per-table files: `people.md`, `player_attributes.md`, `people_roles.md`, `rounds.md` (replacing the old `entities` + `entity_roles`). Output tables get FK updates and `*_associations.md` junction files. Schema overview diagram in `README.md` redrawn.
- **`docs/architecture/01-information-architecture.md`** — describes the entity model conceptually; needs rewrite around typed tables.
- **`docs/agents/system/source-discovery.md`** — Miner's dedupe references entity_id; update to match.
- **`docs/concepts/entity-roles.md`** — rename to `people-roles.md`; rewrite around `people` table.
- This file (`refactor-entities-to-typed-tables.md`) — gets archived once execution is complete.

---

## Risks & rollback

| Risk | Mitigation |
|---|---|
| Phase 1 backfill bug leaves orphaned typed FKs | Phase 1 is purely additive; fix the backfill and re-run before phase 2. Old schema still authoritative until phase 3. |
| Phase 2 code change misses a query | Tests + grep audit. Both old `entity_id` and new typed FK fields readable in parallel until phase 3. |
| Phase 3 destructive migration runs against drifted data | Phase 3 starts with explicit verification queries that fail the migration if drift exists. |
| `UNIQUE NULLS NOT DISTINCT` not supported | Falls back to functional unique index using COALESCE — DDL noted in plan. Postgres 15+ is assumed. |
| Column promotion misses keys present in metadata_json | After backfill, audit any `metadata_json ?| ARRAY['<promoted_key>']` rows and lift them. One-shot UPDATE script. |

---

## Open questions to resolve before phase 1 lands

### Resolved

| # | Question | Decision |
|---|---|---|
| 1 | `rounds` shape | Full typed columns (`is_magic_round`, `is_rep_weekend`, `is_finals` promoted from would-be metadata_json). |
| 1b | Round byes — separate `round_byes` junction or fold into `matches`? | **Fold into `matches`**: `away_team_id` becomes nullable, `'bye'` added to status enum, `home_team_id` overloaded to mean "the team in question" for bye rows. |
| 2 | `source_annotations` polymorphism — keep or drop? | **Drop the table entirely.** Functionality absorbed into a generalised `claims` table; expand `claim_type` enum, add `payload_json`. |
| 3 | `events.related_entity_ids[]` — convert to junction? | **Defer.** Events table left untouched by this refactor; rebuilt as a separate future piece of work. UUIDs in `related_entity_ids[]` become dangling after Phase 3 — accepted. |
| 4 | `people.entity_type` denorm | **Drop entirely.** Coverage is provided by `people_roles`; queries that need "current commentators" JOIN to it directly. |
| 7a | `secondary_positions` — promote to column? | **Skip.** Stays out of `people_attributes` for now; revisit later if needed. |
| 7b | `is_captain` — column on people? | **No — column on `match_team_lists`.** Captain is a per-match-per-team-per-player fact, not a person-level attribute. |
| 7c | `status='retired'` — column? | **Derive** from "no current people_roles row" — don't store. |

### Deferred (not blocking phase 1)

| # | Question | Plan |
|---|---|---|
| 5 | `alignment_scores.entity_id` | Follow typed-nullable + CHECK pattern when the table is built. |
| 6 | `remarks.subject_entity_ids[]` | Use `remark_associations` junction when remarks lands. |
| 8 | `events` redesign | Separate future work. Will sweep dangling `related_entity_ids[]` UUIDs as part of that rebuild. |

---

## What's next if approved

1. Resolve open questions above.
2. Write migration 036 (additive). Per the phase 1 spec.
3. Run `make migrate` against dev.
4. Verify backfill counts: `SELECT COUNT(*) FROM people` equals `SELECT COUNT(*) FROM entities WHERE entity_type IN (person types)`. Same checks per new table.
5. Phase 2 code switchover — separate PR, one focused day's work.
6. Write migration 037 (destructive). Verify-then-execute.
7. Update the data catalogue and other docs.
