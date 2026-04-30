-- 027: player_attributes — consolidated SCD-2 of slow-changing player facts
--
-- Replaces player_team_history (migration 005). PTH carried only team /
-- position; player_attributes adds height, weight, contract. All these
-- change at the same beats (preseason, transfer window, contract renewal)
-- and come from the same source (SC roster scrape today; nrl.com / NSWRL /
-- QRL later), so a single SCD-2 row per current state — closed and reopened
-- on change — is cleaner than two parallel temporal tables.
--
-- The split between this table and its neighbours:
--   entities.metadata_json     — lifetime constants (dob, debut, birth country)
--   entity_roles               — cross-entity-type role tenure (player → coach)
--   player_attributes (here)   — player-specific slow-changing facts
--   player_rounds              — per-round facts (price, breakeven, score,
--                                jersey, grade — players move between NRL
--                                and NSW Cup / Q Cup week to week)
--
-- Convention follows entity_roles (018) and the now-deprecated PTH (005):
-- effective_from / effective_to / is_current denorm. team_id FKs the
-- staged `teams` registry (026) — for a player demoted to a feeder grade
-- mid-season, team_id stays the senior NRL/NRLW row; per-round grade
-- affiliation is captured in player_rounds.

CREATE TABLE IF NOT EXISTS player_attributes (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id        UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    team_id          UUID REFERENCES teams(team_id) ON DELETE SET NULL,
    primary_position TEXT,
    height_cm        INTEGER,
    weight_kg        INTEGER,
    contract_until   DATE,
    real_salary_aud  INTEGER,
    metadata_json    JSONB NOT NULL DEFAULT '{}',
    effective_from   DATE NOT NULL,
    effective_to     DATE,
    is_current       BOOLEAN NOT NULL DEFAULT TRUE,
    source           TEXT NOT NULL DEFAULT 'seed',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_player_attributes_period CHECK (
        effective_to IS NULL OR effective_to >= effective_from
    )
);

-- Hot read path: "current attributes for entity X"
CREATE INDEX IF NOT EXISTS idx_player_attributes_entity_current
  ON player_attributes(entity_id, is_current);

-- Wiki team-page roster: "who's currently on team X"
CREATE INDEX IF NOT EXISTS idx_player_attributes_team_current
  ON player_attributes(team_id, is_current);

-- Exactly one current row per entity. Enforces SCD-2 invariants.
CREATE UNIQUE INDEX IF NOT EXISTS uq_player_attributes_current
  ON player_attributes(entity_id)
  WHERE is_current;

COMMENT ON TABLE player_attributes IS
    'SCD-2 of slow-changing player facts (team affiliation, position, '
    'height, weight, contract). Replaces player_team_history (migration 005). '
    'Per-round facts live in player_rounds; lifetime constants in '
    'entities.metadata_json; cross-role tenure in entity_roles.';

COMMENT ON COLUMN player_attributes.team_id IS
    'Parent club (NRL / NRLW row in teams). For a player demoted to NSW '
    'Cup / Q Cup mid-season, team_id stays the senior team — per-round '
    'grade affiliation is captured in player_rounds.';

COMMENT ON COLUMN player_attributes.metadata_json IS
    'Catch-all for secondary_positions, captain status, retirement marker, '
    'supercoach_id mirroring, etc.';

-- ---------------------------------------------------------------------------
-- Drop deprecated player_team_history (migration 005). No live code paths
-- reference it; the seed script (scripts/data/seed_player_teams.py) is
-- replaced by the player-roster admin endpoints.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS player_team_history;
