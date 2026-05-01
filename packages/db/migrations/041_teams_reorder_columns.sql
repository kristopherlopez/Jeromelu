-- 041: Reorder `teams` columns so `active`, `created_at`, `updated_at` trail
-- `founded_year` and `logo_url`. PostgreSQL has no in-place column reorder;
-- mig 036 added founded_year/logo_url after the original mig 026 had already
-- placed the audit columns at the end, leaving a physically awkward layout.
--
-- This migration rebuilds the table. Single transaction — rolls back cleanly
-- on any failure. 13 FK constraints reference teams.team_id; all are dropped
-- and recreated with identical definitions:
--   ON DELETE CASCADE  — claim_associations, decision_associations,
--                        prediction_associations
--   ON DELETE RESTRICT — match_team_lists, matches.home_team_id,
--                        matches.away_team_id
--   ON DELETE SET NULL — injuries, people_attributes, player_rounds,
--                        teams.parent_team_id (self-FK)
--   no action          — consensus_snapshots, knowledge_base, wiki_pages

BEGIN;

-- ─── 1. New table with desired column order ──────────────────────────

CREATE TABLE teams_new (
    team_id        UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    slug           TEXT         NOT NULL UNIQUE,
    name           TEXT         NOT NULL,
    short_name     TEXT,
    aliases        TEXT[]       NOT NULL DEFAULT '{}',
    grade          TEXT         NOT NULL,
    competition    TEXT,
    parent_team_id UUID,
    founded_year   INTEGER,
    logo_url       TEXT,
    metadata_json  JSONB        NOT NULL DEFAULT '{}'::jsonb,
    active         BOOLEAN      NOT NULL DEFAULT true,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ck_teams_grade CHECK (grade IN (
        'nrl', 'nrlw', 'nsw_cup', 'qld_cup',
        'jersey_flegg', 'mal_meninga', 'sg_ball',
        'cyril_connell', 'harold_matthews'
    )),
    CONSTRAINT ck_teams_grade_self_parent
        CHECK (parent_team_id IS NULL OR parent_team_id <> team_id)
);

-- ─── 2. Copy data ────────────────────────────────────────────────────

INSERT INTO teams_new (
    team_id, slug, name, short_name, aliases, grade, competition,
    parent_team_id, founded_year, logo_url, metadata_json, active,
    created_at, updated_at
)
SELECT
    team_id, slug, name, short_name, aliases, grade, competition,
    parent_team_id, founded_year, logo_url, metadata_json, active,
    created_at, updated_at
FROM teams;

-- ─── 3. Drop FKs from other tables pointing at teams ─────────────────

ALTER TABLE claim_associations      DROP CONSTRAINT claim_associations_team_id_fkey;
ALTER TABLE consensus_snapshots     DROP CONSTRAINT consensus_snapshots_team_id_fkey;
ALTER TABLE decision_associations   DROP CONSTRAINT decision_associations_team_id_fkey;
ALTER TABLE injuries                DROP CONSTRAINT injuries_team_id_fkey;
ALTER TABLE knowledge_base          DROP CONSTRAINT knowledge_base_team_id_fkey;
ALTER TABLE match_team_lists        DROP CONSTRAINT match_team_lists_team_id_fkey;
ALTER TABLE matches                 DROP CONSTRAINT matches_away_team_id_fkey;
ALTER TABLE matches                 DROP CONSTRAINT matches_home_team_id_fkey;
ALTER TABLE people_attributes       DROP CONSTRAINT people_attributes_team_id_fkey;
ALTER TABLE player_rounds           DROP CONSTRAINT player_rounds_team_id_fkey;
ALTER TABLE prediction_associations DROP CONSTRAINT prediction_associations_team_id_fkey;
ALTER TABLE wiki_pages              DROP CONSTRAINT wiki_pages_team_id_fkey;

-- ─── 4. Drop old table (self-FK falls with it) ──────────────────────

DROP TABLE teams;

-- ─── 5. Rename new table ─────────────────────────────────────────────

ALTER TABLE teams_new RENAME TO teams;

-- ─── 6. Recreate indexes (PK + slug UNIQUE come with CREATE TABLE) ──

CREATE INDEX idx_teams_grade  ON teams (grade);
CREATE INDEX idx_teams_parent ON teams (parent_team_id);
CREATE INDEX idx_teams_active ON teams (active);

-- ─── 7. Recreate self-FK ─────────────────────────────────────────────

ALTER TABLE teams
  ADD CONSTRAINT teams_parent_team_id_fkey
  FOREIGN KEY (parent_team_id) REFERENCES teams(team_id) ON DELETE SET NULL;

-- ─── 8. Recreate FKs from other tables ───────────────────────────────

ALTER TABLE claim_associations      ADD CONSTRAINT claim_associations_team_id_fkey      FOREIGN KEY (team_id)      REFERENCES teams(team_id) ON DELETE CASCADE;
ALTER TABLE consensus_snapshots     ADD CONSTRAINT consensus_snapshots_team_id_fkey     FOREIGN KEY (team_id)      REFERENCES teams(team_id);
ALTER TABLE decision_associations   ADD CONSTRAINT decision_associations_team_id_fkey   FOREIGN KEY (team_id)      REFERENCES teams(team_id) ON DELETE CASCADE;
ALTER TABLE injuries                ADD CONSTRAINT injuries_team_id_fkey                FOREIGN KEY (team_id)      REFERENCES teams(team_id) ON DELETE SET NULL;
ALTER TABLE knowledge_base          ADD CONSTRAINT knowledge_base_team_id_fkey          FOREIGN KEY (team_id)      REFERENCES teams(team_id);
ALTER TABLE match_team_lists        ADD CONSTRAINT match_team_lists_team_id_fkey        FOREIGN KEY (team_id)      REFERENCES teams(team_id) ON DELETE RESTRICT;
ALTER TABLE matches                 ADD CONSTRAINT matches_away_team_id_fkey            FOREIGN KEY (away_team_id) REFERENCES teams(team_id) ON DELETE RESTRICT;
ALTER TABLE matches                 ADD CONSTRAINT matches_home_team_id_fkey            FOREIGN KEY (home_team_id) REFERENCES teams(team_id) ON DELETE RESTRICT;
ALTER TABLE people_attributes       ADD CONSTRAINT people_attributes_team_id_fkey       FOREIGN KEY (team_id)      REFERENCES teams(team_id) ON DELETE SET NULL;
ALTER TABLE player_rounds           ADD CONSTRAINT player_rounds_team_id_fkey           FOREIGN KEY (team_id)      REFERENCES teams(team_id) ON DELETE SET NULL;
ALTER TABLE prediction_associations ADD CONSTRAINT prediction_associations_team_id_fkey FOREIGN KEY (team_id)      REFERENCES teams(team_id) ON DELETE CASCADE;
ALTER TABLE wiki_pages              ADD CONSTRAINT wiki_pages_team_id_fkey              FOREIGN KEY (team_id)      REFERENCES teams(team_id);

COMMIT;
