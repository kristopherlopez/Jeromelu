-- 026: teams — canonical roster of every team across all grades feeding into NRL
--
-- Until now, "teams" lived only as `entities` rows with entity_type='team',
-- created lazily when a transcript mentioned them. That works for the NRL
-- top grade but loses the pathway: every NRL club has feeders in NSW Cup /
-- QLD Cup, then Jersey Flegg / Mal Meninga, then SG Ball / Cyril Connell,
-- then Harold Matthews. NRLW sits alongside NRL with its own roster.
--
-- This table is the single roster across all those grades, with a
-- self-referencing parent_team_id that links a feeder team to its senior
-- side (Norths Devils → Brisbane Broncos; Jersey Flegg Panthers → Penrith
-- Panthers; Sunshine Coast Falcons → Melbourne Storm; etc.).
--
-- entity_id links the senior NRL/NRLW row to the existing canonical entity
-- so claims/predictions/wiki pages keep working without duplication. Feeder
-- grades typically don't carry their own entity row — they inherit identity
-- via parent_team_id.

CREATE TABLE IF NOT EXISTS teams (
    team_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug           TEXT NOT NULL UNIQUE,
    name           TEXT NOT NULL,
    short_name     TEXT,
    aliases        TEXT[] NOT NULL DEFAULT '{}',
    grade          TEXT NOT NULL,
    competition    TEXT,
    parent_team_id UUID REFERENCES teams(team_id) ON DELETE SET NULL,
    entity_id      UUID UNIQUE REFERENCES entities(entity_id) ON DELETE SET NULL,
    metadata_json  JSONB NOT NULL DEFAULT '{}',
    active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_teams_grade CHECK (grade IN (
        'nrl',
        'nrlw',
        'nsw_cup',
        'qld_cup',
        'jersey_flegg',
        'mal_meninga',
        'sg_ball',
        'cyril_connell',
        'harold_matthews'
    )),
    CONSTRAINT ck_teams_grade_self_parent CHECK (
        parent_team_id IS NULL OR parent_team_id <> team_id
    )
);

CREATE INDEX IF NOT EXISTS idx_teams_grade   ON teams(grade);
CREATE INDEX IF NOT EXISTS idx_teams_parent  ON teams(parent_team_id);
CREATE INDEX IF NOT EXISTS idx_teams_entity  ON teams(entity_id);
CREATE INDEX IF NOT EXISTS idx_teams_active  ON teams(active);

COMMENT ON TABLE teams IS
    'Canonical roster of every team across all grades feeding into NRL '
    '(NRL, NRLW, NSW Cup, QLD Cup, Jersey Flegg, Mal Meninga, SG Ball, '
    'Cyril Connell, Harold Matthews). parent_team_id links feeders to '
    'their senior NRL/NRLW side; entity_id links senior rows to the '
    'canonical entities row.';

COMMENT ON COLUMN teams.parent_team_id IS
    'Senior team this team feeds into. NULL for top-grade rows '
    '(NRL / NRLW). Self-reference enables recursive CTEs over a club '
    'pathway.';

COMMENT ON COLUMN teams.entity_id IS
    'Canonical entity for this team. Populated for NRL / NRLW rows so '
    'claims/predictions/wiki pages tie back. Feeder grades inherit '
    'identity via parent_team_id and typically leave this NULL.';
