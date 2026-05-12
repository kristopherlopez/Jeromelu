-- team_standings: per-round team-table positions + the 22 per-team metrics
-- from nrl.com /ladder/data.
--
-- One row per (team, season, round). Re-running the same round overwrites.

CREATE TABLE IF NOT EXISTS team_standings (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id                     UUID REFERENCES teams(team_id),
    nrlcom_team_nickname        TEXT NOT NULL,  -- 'Panthers', 'Broncos', etc. — used for lookup if team_id is unresolved
    competition                 INTEGER NOT NULL,
    season                      INTEGER NOT NULL,
    round                       INTEGER NOT NULL,
    ladder_position             INTEGER,  -- 1..17
    movement                    TEXT,     -- 'up', 'down', 'none'
    -- The 22 per-team metrics (stats.* from /ladder/data)
    played                      INTEGER,
    wins                        INTEGER,
    lost                        INTEGER,
    drawn                       INTEGER,
    byes                        INTEGER,
    points                      INTEGER,
    points_for                  INTEGER,
    points_against              INTEGER,
    points_difference           INTEGER,
    bonus_points                INTEGER,
    form                        TEXT,
    streak                      TEXT,
    home_record                 TEXT,
    away_record                 TEXT,
    day_record                  TEXT,
    night_record                TEXT,
    average_winning_margin      REAL,
    average_losing_margin       REAL,
    close_games                 INTEGER,
    golden_point                INTEGER,
    players_used                INTEGER,
    odds                        TEXT,
    raw_payload                 JSONB NOT NULL,
    s3_archive_key              TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_team_standings_team_season_round
    ON team_standings(nrlcom_team_nickname, competition, season, round);

CREATE INDEX IF NOT EXISTS idx_team_standings_team
    ON team_standings(team_id);
CREATE INDEX IF NOT EXISTS idx_team_standings_season_round
    ON team_standings(season, round);
