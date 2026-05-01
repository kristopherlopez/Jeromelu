-- 036: typed identity tables + association junctions (Phase 1, additive)
--
-- Phase 1 of the entities → typed tables refactor. Every change here is
-- additive — old tables and columns continue to work alongside the new
-- ones. Application code switches over in Phase 2 (separate PR). The old
-- entities table, entity_id columns, and player_attributes get dropped in
-- Phase 3 (migration 037).
--
-- See docs/operations/refactor-entities-to-typed-tables.md for the full
-- design rationale.
--
-- What this migration does, in nine sections:
--
--   1. New identity tables: people, people_attributes, people_roles, rounds.
--   2. Backfill those new tables from entities / entity_roles / player_attributes.
--   3. Association junction tables: claim_associations, prediction_associations,
--      decision_associations. Backfill from existing single-subject FKs.
--   4. Add typed FK columns to tables with always-one-kind subjects (quotes,
--      predictions, source_speakers, match_team_lists, injuries). Backfill.
--   5. Add typed nullable FKs + CHECK to single-subject polymorphic tables
--      (wiki_pages, consensus_snapshots, knowledge_base). Backfill by dispatch.
--   6. Drop source_annotations (empty); generalise claims (kind enum + payload_json).
--   7. Matches accommodates bye rows: away_team_id nullable, 'bye' status, CHECK.
--   8. Column promotions on teams / venues / matches.
--   9. is_captain on match_team_lists.
--
-- Design notes worth surfacing inline rather than in the doc:
--
--   - people.person_id intentionally equals entities.entity_id for person-typed
--     rows (same UUID). This means every existing FK that points at a person
--     entity stays referentially valid by simply renaming the column to
--     *_person_id. Same trick for rounds.round_id = entities.entity_id where
--     entity_type='round'.
--
--   - For claim_associations and friends: the CHECK exactly-one constraint
--     uses (col IS NOT NULL)::int + ... = 1 — standard Postgres pattern.
--
--   - UNIQUE NULLS NOT DISTINCT requires PG 15+. If the cluster is older,
--     fall back to functional unique indexes using COALESCE(...).

BEGIN;

-- ═════════════════════════════════════════════════════════════════════════════
-- Section 1 — New identity-layer tables
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS people (
    person_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name TEXT NOT NULL,
    aliases        TEXT[] NOT NULL DEFAULT '{}',
    slug           TEXT UNIQUE,

    -- Stable lifetime facts (promoted from entities.metadata_json)
    dob            DATE,
    country        TEXT,
    image_url      TEXT,
    supercoach_id  INTEGER UNIQUE,

    -- Long-tail / sparse / unstructured. Promote heavily-used keys to columns later.
    metadata_json  JSONB NOT NULL DEFAULT '{}',

    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_people_name    ON people (canonical_name);
CREATE INDEX IF NOT EXISTS idx_people_country ON people (country) WHERE country IS NOT NULL;

COMMENT ON TABLE people IS
    'Unified table for every human actor — players, coaches, advisors, '
    'commentators, journalists, referees. Replaces person-typed entities '
    'rows. Roles tracked via people_roles (multi-valued SCD-2); slow-'
    'changing facts via people_attributes (single-current SCD-2).';


CREATE TABLE IF NOT EXISTS people_attributes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id           UUID NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
    team_id             UUID REFERENCES teams(team_id) ON DELETE SET NULL,
    primary_position    TEXT,
    height_cm           INTEGER,
    weight_kg           INTEGER,
    contract_until      DATE,
    real_salary_aud     INTEGER,
    metadata_json       JSONB NOT NULL DEFAULT '{}',

    effective_from      DATE NOT NULL,
    effective_to        DATE,
    is_current          BOOLEAN NOT NULL DEFAULT TRUE,
    source              TEXT NOT NULL DEFAULT 'seed',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_people_attributes_period
        CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE INDEX IF NOT EXISTS idx_people_attributes_person_current
    ON people_attributes (person_id, is_current);
CREATE INDEX IF NOT EXISTS idx_people_attributes_team_current
    ON people_attributes (team_id, is_current);
CREATE UNIQUE INDEX IF NOT EXISTS uq_people_attributes_current
    ON people_attributes (person_id) WHERE is_current;

COMMENT ON TABLE people_attributes IS
    'SCD-2 of slow-changing per-person facts. Replaces player_attributes '
    '(dropped in mig 037). Closed and reopened on change. Lifetime '
    'constants live on people; per-event facts on player_rounds / '
    'match_team_lists / injuries.';


CREATE TABLE IF NOT EXISTS people_roles (
    role_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id      UUID NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
    role           TEXT NOT NULL,
    effective_from DATE NOT NULL,
    effective_to   DATE,
    is_primary     BOOLEAN NOT NULL DEFAULT FALSE,
    metadata_json  JSONB NOT NULL DEFAULT '{}',
    source         TEXT NOT NULL DEFAULT 'seed',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_people_roles_role
        CHECK (role IN ('player','coach','commentator','journalist','referee','advisor')),
    CONSTRAINT ck_people_roles_period
        CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE INDEX IF NOT EXISTS idx_people_roles_person
    ON people_roles (person_id, effective_to);
CREATE INDEX IF NOT EXISTS idx_people_roles_role_period
    ON people_roles (role, effective_from, effective_to);
CREATE UNIQUE INDEX IF NOT EXISTS uq_people_roles_primary_current
    ON people_roles (person_id) WHERE is_primary AND effective_to IS NULL;

COMMENT ON TABLE people_roles IS
    'SCD-2 of role tenure per person. Multi-valued at a point in time '
    '(e.g. Adam Reynolds = active player + occasional commentator). '
    'Renamed from entity_roles (dropped in mig 037).';


CREATE TABLE IF NOT EXISTS rounds (
    round_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    season             INTEGER NOT NULL,
    round_number       INTEGER,
    round_label        TEXT NOT NULL,
    starts_at          TIMESTAMPTZ,
    ends_at            TIMESTAMPTZ,
    is_magic_round     BOOLEAN NOT NULL DEFAULT FALSE,
    is_rep_weekend     BOOLEAN NOT NULL DEFAULT FALSE,
    is_finals          BOOLEAN NOT NULL DEFAULT FALSE,
    metadata_json      JSONB NOT NULL DEFAULT '{}',

    UNIQUE (season, round_number)
);

CREATE INDEX IF NOT EXISTS idx_rounds_season ON rounds (season);

COMMENT ON TABLE rounds IS
    'Round identity. Replaces entity_type=round entries on entities. '
    'Linked to from claim_associations / prediction_associations / etc. '
    'when an opinion is round-level rather than player- or match-level.';


-- ═════════════════════════════════════════════════════════════════════════════
-- Section 2 — Backfill identity-layer tables from existing data
-- ═════════════════════════════════════════════════════════════════════════════

-- People: backfill from entities (lifting metadata_json keys to typed columns).
-- person_id == entities.entity_id by design — so every existing FK pointing at
-- a person entity stays valid as a reference to person_id.
INSERT INTO people (
    person_id, canonical_name, aliases, slug,
    dob, country, image_url, supercoach_id,
    metadata_json, created_at
)
SELECT
    e.entity_id,
    e.canonical_name,
    e.aliases,
    e.slug,
    -- Lift typed keys; defensive against missing or non-castable values
    CASE WHEN e.metadata_json ? 'dob'
         THEN NULLIF(e.metadata_json->>'dob','')::date END,
    NULLIF(e.metadata_json->>'country',''),
    NULLIF(e.metadata_json->>'image_url',''),
    CASE WHEN e.metadata_json ? 'supercoach_id'
         THEN NULLIF(e.metadata_json->>'supercoach_id','')::int END,
    -- Strip the lifted keys from metadata_json
    e.metadata_json - 'dob' - 'country' - 'image_url' - 'supercoach_id',
    e.created_at
FROM entities e
WHERE e.entity_type IN ('player','coach','referee','commentator','journalist','advisor')
ON CONFLICT (person_id) DO NOTHING;


-- people_attributes: copy from player_attributes; entity_id renamed to person_id.
INSERT INTO people_attributes (
    id, person_id, team_id, primary_position, height_cm, weight_kg,
    contract_until, real_salary_aud, metadata_json,
    effective_from, effective_to, is_current, source, created_at, updated_at
)
SELECT
    id, entity_id, team_id, primary_position, height_cm, weight_kg,
    contract_until, real_salary_aud, metadata_json,
    effective_from, effective_to, is_current, source, created_at, updated_at
FROM player_attributes
ON CONFLICT (id) DO NOTHING;


-- people_roles: copy from entity_roles; entity_role_id renamed to role_id.
INSERT INTO people_roles (
    role_id, person_id, role, effective_from, effective_to, is_primary,
    metadata_json, source, created_at, updated_at
)
SELECT
    entity_role_id, entity_id, role, effective_from, effective_to, is_primary,
    metadata_json, source, created_at, updated_at
FROM entity_roles
ON CONFLICT (role_id) DO NOTHING;


-- Rounds: parse from entities[entity_type='round']. canonical_name is the
-- round label; season / round_number live in metadata_json (best-effort).
INSERT INTO rounds (
    round_id, season, round_number, round_label, metadata_json
)
SELECT
    e.entity_id,
    COALESCE(
        NULLIF(e.metadata_json->>'season','')::int,
        EXTRACT(YEAR FROM now())::int                    -- fallback: current year
    ),
    NULLIF(e.metadata_json->>'round_number','')::int,    -- NULL for finals/magic
    e.canonical_name,
    e.metadata_json - 'season' - 'round_number'
FROM entities e
WHERE e.entity_type = 'round'
ON CONFLICT (round_id) DO NOTHING;


-- ═════════════════════════════════════════════════════════════════════════════
-- Section 3 — Association junction tables + backfill
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS claim_associations (
    association_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id       UUID NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    role           TEXT NOT NULL,
    person_id      UUID REFERENCES people(person_id)   ON DELETE CASCADE,
    team_id        UUID REFERENCES teams(team_id)      ON DELETE CASCADE,
    match_id       UUID REFERENCES matches(match_id)   ON DELETE CASCADE,
    venue_id       UUID REFERENCES venues(venue_id)    ON DELETE CASCADE,
    round_id       UUID REFERENCES rounds(round_id)    ON DELETE CASCADE,

    CONSTRAINT ck_claim_associations_one_subject CHECK (
        (person_id IS NOT NULL)::int +
        (team_id   IS NOT NULL)::int +
        (match_id  IS NOT NULL)::int +
        (venue_id  IS NOT NULL)::int +
        (round_id  IS NOT NULL)::int = 1
    ),

    -- PG 15+ syntax: NULLS NOT DISTINCT prevents duplicate (claim, role, X) rows.
    -- If on PG < 15, fall back to a functional unique index over COALESCE(...).
    CONSTRAINT uq_claim_associations
        UNIQUE NULLS NOT DISTINCT
        (claim_id, role, person_id, team_id, match_id, venue_id, round_id)
);

CREATE INDEX IF NOT EXISTS idx_claim_associations_claim   ON claim_associations (claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_associations_person  ON claim_associations (person_id) WHERE person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_claim_associations_team    ON claim_associations (team_id)   WHERE team_id   IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_claim_associations_match   ON claim_associations (match_id)  WHERE match_id  IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_claim_associations_venue   ON claim_associations (venue_id)  WHERE venue_id  IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_claim_associations_round   ON claim_associations (round_id)  WHERE round_id  IS NOT NULL;


CREATE TABLE IF NOT EXISTS prediction_associations (
    association_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id  UUID NOT NULL REFERENCES predictions(prediction_id) ON DELETE CASCADE,
    role           TEXT NOT NULL,
    person_id      UUID REFERENCES people(person_id)   ON DELETE CASCADE,
    team_id        UUID REFERENCES teams(team_id)      ON DELETE CASCADE,
    match_id       UUID REFERENCES matches(match_id)   ON DELETE CASCADE,
    venue_id       UUID REFERENCES venues(venue_id)    ON DELETE CASCADE,
    round_id       UUID REFERENCES rounds(round_id)    ON DELETE CASCADE,

    CONSTRAINT ck_prediction_associations_one_subject CHECK (
        (person_id IS NOT NULL)::int +
        (team_id   IS NOT NULL)::int +
        (match_id  IS NOT NULL)::int +
        (venue_id  IS NOT NULL)::int +
        (round_id  IS NOT NULL)::int = 1
    ),
    CONSTRAINT uq_prediction_associations
        UNIQUE NULLS NOT DISTINCT
        (prediction_id, role, person_id, team_id, match_id, venue_id, round_id)
);

CREATE INDEX IF NOT EXISTS idx_prediction_associations_prediction ON prediction_associations (prediction_id);
CREATE INDEX IF NOT EXISTS idx_prediction_associations_person     ON prediction_associations (person_id) WHERE person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_prediction_associations_team       ON prediction_associations (team_id)   WHERE team_id   IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_prediction_associations_match      ON prediction_associations (match_id)  WHERE match_id  IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_prediction_associations_venue      ON prediction_associations (venue_id)  WHERE venue_id  IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_prediction_associations_round      ON prediction_associations (round_id)  WHERE round_id  IS NOT NULL;


CREATE TABLE IF NOT EXISTS decision_associations (
    association_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id    UUID NOT NULL REFERENCES decisions(decision_id) ON DELETE CASCADE,
    role           TEXT NOT NULL,
    person_id      UUID REFERENCES people(person_id)   ON DELETE CASCADE,
    team_id        UUID REFERENCES teams(team_id)      ON DELETE CASCADE,
    match_id       UUID REFERENCES matches(match_id)   ON DELETE CASCADE,
    venue_id       UUID REFERENCES venues(venue_id)    ON DELETE CASCADE,
    round_id       UUID REFERENCES rounds(round_id)    ON DELETE CASCADE,

    CONSTRAINT ck_decision_associations_one_subject CHECK (
        (person_id IS NOT NULL)::int +
        (team_id   IS NOT NULL)::int +
        (match_id  IS NOT NULL)::int +
        (venue_id  IS NOT NULL)::int +
        (round_id  IS NOT NULL)::int = 1
    ),
    CONSTRAINT uq_decision_associations
        UNIQUE NULLS NOT DISTINCT
        (decision_id, role, person_id, team_id, match_id, venue_id, round_id)
);

CREATE INDEX IF NOT EXISTS idx_decision_associations_decision ON decision_associations (decision_id);
CREATE INDEX IF NOT EXISTS idx_decision_associations_person   ON decision_associations (person_id) WHERE person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_decision_associations_team     ON decision_associations (team_id)   WHERE team_id   IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_decision_associations_match    ON decision_associations (match_id)  WHERE match_id  IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_decision_associations_venue    ON decision_associations (venue_id)  WHERE venue_id  IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_decision_associations_round    ON decision_associations (round_id)  WHERE round_id  IS NOT NULL;


-- Backfill claim_associations from claims.subject_entity_id, dispatching by
-- entity_type. Each existing claim with a subject becomes one row with role='subject'.
INSERT INTO claim_associations (claim_id, role, person_id, team_id, match_id, venue_id, round_id)
SELECT
    c.claim_id,
    'subject',
    CASE WHEN e.entity_type IN ('player','coach','referee','commentator','journalist','advisor')
         THEN e.entity_id END,
    t.team_id,
    m.match_id,
    v.venue_id,
    CASE WHEN e.entity_type='round' THEN e.entity_id END
FROM claims c
JOIN entities e ON c.subject_entity_id = e.entity_id
LEFT JOIN teams   t ON e.entity_type='team'   AND t.entity_id  = e.entity_id
LEFT JOIN matches m ON e.entity_type='match'  AND m.entity_id  = e.entity_id
LEFT JOIN venues  v ON e.entity_type='venue'  AND v.entity_id  = e.entity_id
WHERE c.subject_entity_id IS NOT NULL
ON CONFLICT DO NOTHING;


-- Backfill prediction_associations: same dispatch from predictions.subject_entity_id.
INSERT INTO prediction_associations (prediction_id, role, person_id, team_id, match_id, venue_id, round_id)
SELECT
    p.prediction_id,
    'subject',
    CASE WHEN e.entity_type IN ('player','coach','referee','commentator','journalist','advisor')
         THEN e.entity_id END,
    t.team_id,
    m.match_id,
    v.venue_id,
    CASE WHEN e.entity_type='round' THEN e.entity_id END
FROM predictions p
JOIN entities e ON p.subject_entity_id = e.entity_id
LEFT JOIN teams   t ON e.entity_type='team'   AND t.entity_id  = e.entity_id
LEFT JOIN matches m ON e.entity_type='match'  AND m.entity_id  = e.entity_id
LEFT JOIN venues  v ON e.entity_type='venue'  AND v.entity_id  = e.entity_id
WHERE p.subject_entity_id IS NOT NULL
ON CONFLICT DO NOTHING;


-- Backfill decision_associations: same dispatch from decisions.subject_entity_id.
INSERT INTO decision_associations (decision_id, role, person_id, team_id, match_id, venue_id, round_id)
SELECT
    d.decision_id,
    'subject',
    CASE WHEN e.entity_type IN ('player','coach','referee','commentator','journalist','advisor')
         THEN e.entity_id END,
    t.team_id,
    m.match_id,
    v.venue_id,
    CASE WHEN e.entity_type='round' THEN e.entity_id END
FROM decisions d
JOIN entities e ON d.subject_entity_id = e.entity_id
LEFT JOIN teams   t ON e.entity_type='team'   AND t.entity_id  = e.entity_id
LEFT JOIN matches m ON e.entity_type='match'  AND m.entity_id  = e.entity_id
LEFT JOIN venues  v ON e.entity_type='venue'  AND v.entity_id  = e.entity_id
WHERE d.subject_entity_id IS NOT NULL
ON CONFLICT DO NOTHING;


-- ═════════════════════════════════════════════════════════════════════════════
-- Section 4 — Add typed FK columns alongside entity_id (always-one-kind)
-- ═════════════════════════════════════════════════════════════════════════════

ALTER TABLE quotes              ADD COLUMN IF NOT EXISTS speaker_person_id  UUID REFERENCES people(person_id);
ALTER TABLE predictions         ADD COLUMN IF NOT EXISTS predictor_person_id UUID REFERENCES people(person_id);
ALTER TABLE source_speakers     ADD COLUMN IF NOT EXISTS speaker_person_id  UUID REFERENCES people(person_id);
ALTER TABLE match_team_lists    ADD COLUMN IF NOT EXISTS player_id          UUID REFERENCES people(person_id);
ALTER TABLE injuries            ADD COLUMN IF NOT EXISTS player_id          UUID REFERENCES people(person_id);

-- Backfill — entity_id == person_id by design for person-typed entities,
-- so we just copy the value across.
UPDATE quotes
   SET speaker_person_id = speaker_entity_id
 WHERE speaker_entity_id IS NOT NULL AND speaker_person_id IS NULL;

UPDATE predictions
   SET predictor_person_id = predictor_entity_id
 WHERE predictor_entity_id IS NOT NULL AND predictor_person_id IS NULL;

UPDATE source_speakers
   SET speaker_person_id = speaker_entity_id
 WHERE speaker_entity_id IS NOT NULL AND speaker_person_id IS NULL;

UPDATE match_team_lists
   SET player_id = player_entity_id
 WHERE player_entity_id IS NOT NULL AND player_id IS NULL;

UPDATE injuries
   SET player_id = player_entity_id
 WHERE player_entity_id IS NOT NULL AND player_id IS NULL;


-- ═════════════════════════════════════════════════════════════════════════════
-- Section 5 — Single-subject polymorphic tables: typed nullable FKs
-- ═════════════════════════════════════════════════════════════════════════════

-- wiki_pages already has entity_id (any kind) + channel_id.
-- Add typed nullable FKs for each kind; backfill by dispatching on entity_type.
ALTER TABLE wiki_pages
    ADD COLUMN IF NOT EXISTS person_id UUID REFERENCES people(person_id),
    ADD COLUMN IF NOT EXISTS team_id   UUID REFERENCES teams(team_id),
    ADD COLUMN IF NOT EXISTS match_id  UUID REFERENCES matches(match_id),
    ADD COLUMN IF NOT EXISTS venue_id  UUID REFERENCES venues(venue_id),
    ADD COLUMN IF NOT EXISTS round_id  UUID REFERENCES rounds(round_id);

UPDATE wiki_pages w
   SET person_id = e.entity_id
  FROM entities e
 WHERE w.entity_id = e.entity_id
   AND e.entity_type IN ('player','coach','referee','commentator','journalist','advisor')
   AND w.person_id IS NULL;

UPDATE wiki_pages w
   SET team_id = t.team_id
  FROM entities e, teams t
 WHERE w.entity_id = e.entity_id AND e.entity_type='team'
   AND t.entity_id = e.entity_id
   AND w.team_id IS NULL;

UPDATE wiki_pages w
   SET match_id = m.match_id
  FROM entities e, matches m
 WHERE w.entity_id = e.entity_id AND e.entity_type='match'
   AND m.entity_id = e.entity_id
   AND w.match_id IS NULL;

UPDATE wiki_pages w
   SET venue_id = v.venue_id
  FROM entities e, venues v
 WHERE w.entity_id = e.entity_id AND e.entity_type='venue'
   AND v.entity_id = e.entity_id
   AND w.venue_id IS NULL;

UPDATE wiki_pages w
   SET round_id = w.entity_id
  FROM entities e
 WHERE w.entity_id = e.entity_id AND e.entity_type='round'
   AND w.round_id IS NULL;

-- (ck_wiki_page_subject CHECK gets tightened in mig 037 once entity_id is dropped.)


-- consensus_snapshots — same pattern
ALTER TABLE consensus_snapshots
    ADD COLUMN IF NOT EXISTS person_id UUID REFERENCES people(person_id),
    ADD COLUMN IF NOT EXISTS team_id   UUID REFERENCES teams(team_id),
    ADD COLUMN IF NOT EXISTS match_id  UUID REFERENCES matches(match_id),
    ADD COLUMN IF NOT EXISTS venue_id  UUID REFERENCES venues(venue_id),
    ADD COLUMN IF NOT EXISTS round_id  UUID REFERENCES rounds(round_id);

UPDATE consensus_snapshots s
   SET person_id = e.entity_id
  FROM entities e
 WHERE s.subject_entity_id = e.entity_id
   AND e.entity_type IN ('player','coach','referee','commentator','journalist','advisor')
   AND s.person_id IS NULL;

UPDATE consensus_snapshots s
   SET team_id = t.team_id
  FROM entities e, teams t
 WHERE s.subject_entity_id = e.entity_id AND e.entity_type='team'
   AND t.entity_id = e.entity_id
   AND s.team_id IS NULL;

UPDATE consensus_snapshots s
   SET match_id = m.match_id
  FROM entities e, matches m
 WHERE s.subject_entity_id = e.entity_id AND e.entity_type='match'
   AND m.entity_id = e.entity_id
   AND s.match_id IS NULL;

UPDATE consensus_snapshots s
   SET venue_id = v.venue_id
  FROM entities e, venues v
 WHERE s.subject_entity_id = e.entity_id AND e.entity_type='venue'
   AND v.entity_id = e.entity_id
   AND s.venue_id IS NULL;

UPDATE consensus_snapshots s
   SET round_id = s.subject_entity_id
  FROM entities e
 WHERE s.subject_entity_id = e.entity_id AND e.entity_type='round'
   AND s.round_id IS NULL;


-- knowledge_base — same pattern
ALTER TABLE knowledge_base
    ADD COLUMN IF NOT EXISTS person_id UUID REFERENCES people(person_id),
    ADD COLUMN IF NOT EXISTS team_id   UUID REFERENCES teams(team_id),
    ADD COLUMN IF NOT EXISTS match_id  UUID REFERENCES matches(match_id),
    ADD COLUMN IF NOT EXISTS venue_id  UUID REFERENCES venues(venue_id),
    ADD COLUMN IF NOT EXISTS round_id  UUID REFERENCES rounds(round_id);

UPDATE knowledge_base k
   SET person_id = e.entity_id
  FROM entities e
 WHERE k.subject_entity_id = e.entity_id
   AND e.entity_type IN ('player','coach','referee','commentator','journalist','advisor')
   AND k.person_id IS NULL;

UPDATE knowledge_base k
   SET team_id = t.team_id
  FROM entities e, teams t
 WHERE k.subject_entity_id = e.entity_id AND e.entity_type='team'
   AND t.entity_id = e.entity_id
   AND k.team_id IS NULL;

UPDATE knowledge_base k
   SET match_id = m.match_id
  FROM entities e, matches m
 WHERE k.subject_entity_id = e.entity_id AND e.entity_type='match'
   AND m.entity_id = e.entity_id
   AND k.match_id IS NULL;

UPDATE knowledge_base k
   SET venue_id = v.venue_id
  FROM entities e, venues v
 WHERE k.subject_entity_id = e.entity_id AND e.entity_type='venue'
   AND v.entity_id = e.entity_id
   AND k.venue_id IS NULL;

UPDATE knowledge_base k
   SET round_id = k.subject_entity_id
  FROM entities e
 WHERE k.subject_entity_id = e.entity_id AND e.entity_type='round'
   AND k.round_id IS NULL;


-- ═════════════════════════════════════════════════════════════════════════════
-- Section 6 — Drop source_annotations, generalise claims
-- ═════════════════════════════════════════════════════════════════════════════

-- source_annotations was created in mig 034 and has no production rows yet.
-- Functionality absorbed into a generalised claims table (kind enum expansion +
-- payload_json column).
DROP TABLE IF EXISTS source_annotations;

-- Expand claim_type enum to absorb annotation-flavoured kinds.
ALTER TABLE claims DROP CONSTRAINT IF EXISTS ck_claim_type;
ALTER TABLE claims ADD CONSTRAINT ck_claim_type CHECK (claim_type IN (
    -- Fantasy-actionable (existing)
    'buy', 'sell', 'hold', 'captain', 'avoid', 'breakout', 'matchup_edge',
    -- Annotation-flavoured (new — absorbed from source_annotations)
    'mention', 'theme', 'subtopic', 'sentiment', 'tactical_tag', 'highlight'
));

ALTER TABLE claims ADD COLUMN IF NOT EXISTS payload_json JSONB NOT NULL DEFAULT '{}';

COMMENT ON COLUMN claims.claim_type IS
    'What kind of claim/annotation this is. Fantasy-actionable claims '
    '(buy, sell, hold, captain, avoid, breakout, matchup_edge) drive the '
    'Ledger. Annotation kinds (mention, theme, subtopic, sentiment, '
    'tactical_tag, highlight) are softer extractions used for retrieval '
    'and context.';


-- ═════════════════════════════════════════════════════════════════════════════
-- Section 7 — Matches accommodates bye rows
-- ═════════════════════════════════════════════════════════════════════════════

-- Bye rows: home_team_id = team on bye, away_team_id = NULL, status = 'bye',
-- everything else NULL. home_team_id is overloaded for byes — it just means
-- "the team in question," not literally "home team." Match queries that don't
-- want byes filter `WHERE status<>'bye'` or `WHERE away_team_id IS NOT NULL`.
ALTER TABLE matches ALTER COLUMN away_team_id DROP NOT NULL;

ALTER TABLE matches DROP CONSTRAINT IF EXISTS ck_matches_status;
ALTER TABLE matches ADD CONSTRAINT ck_matches_status CHECK (
    status IN ('scheduled','live','final','postponed','cancelled','forfeit','bye')
);

ALTER TABLE matches DROP CONSTRAINT IF EXISTS ck_matches_bye_no_opponent;
ALTER TABLE matches ADD CONSTRAINT ck_matches_bye_no_opponent CHECK (
    (status='bye'  AND away_team_id IS NULL)
    OR (status<>'bye' AND away_team_id IS NOT NULL)
);

-- ck_matches_distinct_teams (home_team_id <> away_team_id) and ck_matches_score_paired
-- (both NULL or both set) both stay correct: NULL≠X is NULL → CHECK passes; both
-- scores NULL is fine for byes.

-- Bye backfill is left to the NRL.com fixture sync going forward — there is no
-- historical bye data outside the draw API to lift.


-- ═════════════════════════════════════════════════════════════════════════════
-- Section 8 — Column promotions on typed entities
-- ═════════════════════════════════════════════════════════════════════════════

-- teams: primary_colour, secondary_colour, founded_year, home_venue_id, logo_url
ALTER TABLE teams
    ADD COLUMN IF NOT EXISTS primary_colour    TEXT,
    ADD COLUMN IF NOT EXISTS secondary_colour  TEXT,
    ADD COLUMN IF NOT EXISTS founded_year      INTEGER,
    ADD COLUMN IF NOT EXISTS home_venue_id     UUID REFERENCES venues(venue_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS logo_url          TEXT;

UPDATE teams
   SET primary_colour    = NULLIF(metadata_json->>'primary_colour',''),
       secondary_colour  = NULLIF(metadata_json->>'secondary_colour',''),
       founded_year      = CASE WHEN metadata_json ? 'founded_year'
                                THEN NULLIF(metadata_json->>'founded_year','')::int END,
       logo_url          = NULLIF(metadata_json->>'logo_url','')
 WHERE metadata_json ?| ARRAY['primary_colour','secondary_colour','founded_year','logo_url'];

UPDATE teams
   SET metadata_json = metadata_json
                       - 'primary_colour'
                       - 'secondary_colour'
                       - 'founded_year'
                       - 'logo_url'
 WHERE metadata_json ?| ARRAY['primary_colour','secondary_colour','founded_year','logo_url'];

-- home_venue_id is left NULL; cannot be reliably resolved from metadata_json
-- shape today. Backfill in a separate manual step if needed.


-- venues: latitude, longitude, opened_year, image_url
ALTER TABLE venues
    ADD COLUMN IF NOT EXISTS latitude     NUMERIC(9, 6),
    ADD COLUMN IF NOT EXISTS longitude    NUMERIC(9, 6),
    ADD COLUMN IF NOT EXISTS opened_year  INTEGER,
    ADD COLUMN IF NOT EXISTS image_url    TEXT;

UPDATE venues
   SET latitude    = CASE WHEN metadata_json ? 'latitude'
                          THEN NULLIF(metadata_json->>'latitude','')::numeric END,
       longitude   = CASE WHEN metadata_json ? 'longitude'
                          THEN NULLIF(metadata_json->>'longitude','')::numeric END,
       opened_year = CASE WHEN metadata_json ? 'opened_year'
                          THEN NULLIF(metadata_json->>'opened_year','')::int END,
       image_url   = NULLIF(metadata_json->>'image_url','')
 WHERE metadata_json ?| ARRAY['latitude','longitude','opened_year','image_url'];

UPDATE venues
   SET metadata_json = metadata_json
                       - 'latitude'
                       - 'longitude'
                       - 'opened_year'
                       - 'image_url'
 WHERE metadata_json ?| ARRAY['latitude','longitude','opened_year','image_url'];


-- matches: is_magic_round, is_rep_weekend
ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS is_magic_round  BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_rep_weekend  BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE matches
   SET is_magic_round = COALESCE((metadata_json->>'is_magic_round')::boolean, FALSE),
       is_rep_weekend = COALESCE((metadata_json->>'is_rep_weekend')::boolean, FALSE)
 WHERE metadata_json ?| ARRAY['is_magic_round','is_rep_weekend'];

UPDATE matches
   SET metadata_json = metadata_json - 'is_magic_round' - 'is_rep_weekend'
 WHERE metadata_json ?| ARRAY['is_magic_round','is_rep_weekend'];


-- ═════════════════════════════════════════════════════════════════════════════
-- Section 9 — is_captain on match_team_lists
-- ═════════════════════════════════════════════════════════════════════════════

-- Captain is a per-match-per-team-per-player fact, not a person attribute.
-- Set to FALSE for existing rows; future named-17 announcements populate it
-- from the NRL.com data. If any historical rows captured captain status in
-- player_attributes.metadata_json, those don't migrate (the cardinality is
-- wrong — captain varies per match, not per SCD-2 attribute window).
ALTER TABLE match_team_lists ADD COLUMN IF NOT EXISTS is_captain BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN match_team_lists.is_captain IS
    'Whether this player was named captain for this match. Per-match-per-'
    'team-per-player; not a person-level attribute (a player can captain '
    'one week and not another).';


COMMIT;

-- ═════════════════════════════════════════════════════════════════════════════
-- Post-migration sanity counts (run separately, not part of the transaction)
-- ═════════════════════════════════════════════════════════════════════════════
--
-- SELECT 'people' AS t, COUNT(*) FROM people
-- UNION ALL SELECT 'people_attributes', COUNT(*) FROM people_attributes
-- UNION ALL SELECT 'people_roles', COUNT(*) FROM people_roles
-- UNION ALL SELECT 'rounds', COUNT(*) FROM rounds
-- UNION ALL SELECT 'claim_associations', COUNT(*) FROM claim_associations
-- UNION ALL SELECT 'prediction_associations', COUNT(*) FROM prediction_associations
-- UNION ALL SELECT 'decision_associations', COUNT(*) FROM decision_associations;
--
-- Expected:
--   people           ≈ COUNT(entities WHERE entity_type IN (person types))
--   people_attributes = COUNT(player_attributes)
--   people_roles      = COUNT(entity_roles)
--   rounds            = COUNT(entities WHERE entity_type='round')
--   claim_associations ≈ COUNT(claims WHERE subject_entity_id IS NOT NULL)
--   (similarly for prediction / decision)
