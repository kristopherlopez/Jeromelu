-- 035: rename discovered_sources → scout_candidates
--
-- Naming alignment. Working tables that hold an agent's pre-promotion
-- queue should carry the agent's id as a prefix — `scout_candidates`
-- (Scout's review queue) reads more clearly than `discovered_sources`,
-- which collides semantically with the canonical `sources` table even
-- though the row may be a channel candidate, not a source candidate.
--
-- Pure rename — no data migration, no shape change. Indexes and CHECK
-- constraints are renamed in place. The original UNIQUE constraint on
-- (platform, kind, external_id) was created inline in migration 017
-- with the postgres-default name; recreated here with the explicit
-- `uq_scout_candidates_platform_kind_external` name to match the
-- house convention going forward.
--
-- Past migrations (017, 020, 022, 023) reference `discovered_sources`
-- directly — those are immutable history and stay untouched. Nothing
-- in those migrations re-runs.

-- Table
ALTER TABLE discovered_sources RENAME TO scout_candidates;

-- Indexes
ALTER INDEX IF EXISTS idx_discovered_status RENAME TO idx_scout_candidates_status;
ALTER INDEX IF EXISTS idx_discovered_kind   RENAME TO idx_scout_candidates_kind;
ALTER INDEX IF EXISTS idx_discovered_run    RENAME TO idx_scout_candidates_run;
ALTER INDEX IF EXISTS idx_discovered_at     RENAME TO idx_scout_candidates_at;

-- CHECK constraints
ALTER TABLE scout_candidates
    RENAME CONSTRAINT ck_discovered_kind   TO ck_scout_candidates_kind;
ALTER TABLE scout_candidates
    RENAME CONSTRAINT ck_discovered_status TO ck_scout_candidates_status;

-- UNIQUE constraint — drop both possible prior names (the postgres-default
-- inline name from mig 017, and the explicit-named one if it existed) and
-- recreate with the canonical convention. Inside the same transaction so
-- there is no window of broken uniqueness.
ALTER TABLE scout_candidates
    DROP CONSTRAINT IF EXISTS discovered_sources_platform_kind_external_id_key;
ALTER TABLE scout_candidates
    DROP CONSTRAINT IF EXISTS uq_discovered_platform_kind_external;
ALTER TABLE scout_candidates
    ADD CONSTRAINT uq_scout_candidates_platform_kind_external
    UNIQUE (platform, kind, external_id);

COMMENT ON TABLE scout_candidates IS
    'Scout''s candidate inbox. Scout writes here while hunting the web for '
    'new NRL channels and videos worth onboarding. Humans approve or reject '
    'via the admin review queue; approval promotes a row into the canonical '
    'channels (kind=channel) or sources (kind=video) tables. Renamed from '
    'discovered_sources in mig 035.';
