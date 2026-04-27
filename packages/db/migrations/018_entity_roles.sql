-- 018: Entity roles (SCD-2) + expanded people entity types
--
-- Lets a single entity carry multiple roles over time without duplicating
-- identity. Andrew Johns (ex-player → commentator), Michael Ennis (player →
-- coach + commentator), Adam Reynolds (active player + occasional commentator)
-- all stay as one entity row with multiple entity_roles rows.
--
-- Conventions follow player_team_history (migration 005):
--   effective_from / effective_to / is_current denorm pattern.
--
-- entity_type stays denormalised — it equals the role on the entity_roles row
-- where is_primary = TRUE AND effective_to IS NULL.

-- ---------------------------------------------------------------------------
-- 1. Extend entities.entity_type — add coach/referee/commentator/journalist,
--    drop the redundant 'expert' (verified zero rows pre-migration)
-- ---------------------------------------------------------------------------
ALTER TABLE entities DROP CONSTRAINT IF EXISTS ck_entity_type;
ALTER TABLE entities DROP CONSTRAINT IF EXISTS entities_entity_type_check;
ALTER TABLE entities ADD CONSTRAINT ck_entity_type
  CHECK (entity_type IN (
    'player',
    'team',
    'advisor',
    'coach',
    'referee',
    'commentator',
    'journalist',
    'matchup',
    'round'
  ));

-- ---------------------------------------------------------------------------
-- 2. entity_roles — role tenure (SCD-2)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS entity_roles (
    entity_role_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    effective_from  DATE NOT NULL,
    effective_to    DATE,
    is_primary      BOOLEAN NOT NULL DEFAULT FALSE,
    metadata_json   JSONB NOT NULL DEFAULT '{}',
    source          TEXT NOT NULL DEFAULT 'seed',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_entity_roles_role CHECK (
        role IN ('player', 'coach', 'commentator', 'journalist', 'referee', 'advisor')
    ),
    CONSTRAINT ck_entity_roles_period CHECK (
        effective_to IS NULL OR effective_to >= effective_from
    )
);

-- "Roles for entity X, current first" + "is the role current?"
CREATE INDEX IF NOT EXISTS idx_entity_roles_entity
  ON entity_roles(entity_id, effective_to);

-- "Who held role R during period P"
CREATE INDEX IF NOT EXISTS idx_entity_roles_role_period
  ON entity_roles(role, effective_from, effective_to);

-- Exactly one primary current role per entity
CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_roles_primary_current
  ON entity_roles(entity_id)
  WHERE is_primary AND effective_to IS NULL;

-- ---------------------------------------------------------------------------
-- 3. Backfill — one primary current role per existing person-entity
--    Non-people types (team, round, matchup) get no entity_roles row.
-- ---------------------------------------------------------------------------
INSERT INTO entity_roles (
    entity_id, role, effective_from, is_primary, source
)
SELECT
    e.entity_id,
    e.entity_type,
    CURRENT_DATE,
    TRUE,
    'backfill_018'
FROM entities e
WHERE e.entity_type IN (
    'player', 'advisor', 'coach', 'referee', 'commentator', 'journalist'
)
  AND NOT EXISTS (
    SELECT 1 FROM entity_roles er
    WHERE er.entity_id = e.entity_id
      AND er.is_primary
      AND er.effective_to IS NULL
);
