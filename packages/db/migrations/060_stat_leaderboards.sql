-- stat_leaderboards: pre-computed top-25 leaderboards from nrl.com /stats/data.
--
-- One row per (category, subgroup, stat, season, position-in-leaders).
-- The nrl.com response groups: playerStats[].groups[].stats[].leaders[]
-- and a parallel teamStats[]. We flatten that into one wide table for
-- easy querying.

CREATE TABLE IF NOT EXISTS stat_leaderboards (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    competition         INTEGER NOT NULL,
    season              INTEGER NOT NULL,
    -- Hierarchy: scope = 'player' | 'team'
    scope               TEXT NOT NULL CHECK (scope IN ('player', 'team')),
    category            TEXT NOT NULL,  -- 'Scoring', 'Attack', 'Passing', ...
    subgroup            TEXT NOT NULL,  -- 'Points', 'Tries', 'Goals', ...
    stat_id             INTEGER,
    stat_title          TEXT NOT NULL,  -- 'Total Points', 'Tries per Game', ...
    -- Leader info
    leader_position     INTEGER NOT NULL,  -- 1..25
    leader_first_name   TEXT,
    leader_last_name    TEXT,
    leader_team_nickname TEXT,
    leader_value        REAL,
    person_id           UUID REFERENCES people(person_id),  -- nullable; resolved by extractor for scope='player'
    team_id             UUID REFERENCES teams(team_id),     -- nullable; resolved for scope='team'
    raw_payload         JSONB NOT NULL,
    s3_archive_key      TEXT,
    captured_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Idempotency: same season + scope + stat + leader-position → same row.
-- A re-fetch updates the value (in case nrl.com revised stats post-game).
CREATE UNIQUE INDEX IF NOT EXISTS uq_stat_leaderboards_lookup
    ON stat_leaderboards(competition, season, scope, category, subgroup, stat_title, leader_position);

CREATE INDEX IF NOT EXISTS idx_stat_leaderboards_season
    ON stat_leaderboards(season);
CREATE INDEX IF NOT EXISTS idx_stat_leaderboards_person
    ON stat_leaderboards(person_id) WHERE person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_stat_leaderboards_team
    ON stat_leaderboards(team_id) WHERE team_id IS NOT NULL;
