-- 029: matches — fixture / result spine.
--
-- The missing centrepiece of the data model. Until now there was no
-- table representing a single game (Broncos v Storm, Round 9, Friday
-- 8pm, Suncorp, status=upcoming, scores=...). Player-level data on
-- player_rounds carried free-text `opposition` and `venue` columns but
-- no canonical match identity.
--
-- One row per game across grades (NRL, NRLW, NSW Cup, QLD Cup, …) — we
-- mirror the grade enum from the teams registry (026). external_match_id
-- holds the upstream feed id (nrl.com matchId, supercoach gameId, …) so
-- the daily fixture-sync upsert is keyed on (season, grade, source +
-- external id) without introducing collisions across feeds.
--
-- Joins:
--   matches.home_team_id / away_team_id  → teams.team_id   (RESTRICT)
--   matches.venue_id                     → venues.venue_id  (SET NULL)
--   player_rounds.match_id (mig 032)     → matches.match_id (SET NULL)
--   match_team_lists.match_id (mig 030)  → matches.match_id (CASCADE)

CREATE TABLE IF NOT EXISTS matches (
    match_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Provenance / upsert key
    source            TEXT NOT NULL DEFAULT 'nrl_com',
    external_match_id TEXT,

    -- Competition placement
    season            INTEGER NOT NULL,
    round             INTEGER,
    round_label       TEXT,
    grade             TEXT NOT NULL,

    -- Participants
    home_team_id      UUID NOT NULL REFERENCES teams(team_id) ON DELETE RESTRICT,
    away_team_id      UUID NOT NULL REFERENCES teams(team_id) ON DELETE RESTRICT,
    venue_id          UUID REFERENCES venues(venue_id) ON DELETE SET NULL,

    -- Schedule + status
    kickoff_at        TIMESTAMPTZ,
    status            TEXT NOT NULL DEFAULT 'scheduled',

    -- Result
    home_score        INTEGER,
    away_score        INTEGER,

    -- Context
    weather           TEXT,
    referee_name      TEXT,
    broadcast         TEXT,
    metadata_json     JSONB NOT NULL DEFAULT '{}',

    -- Sync bookkeeping
    last_synced_at    TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_matches_grade CHECK (grade IN (
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
    CONSTRAINT ck_matches_status CHECK (status IN (
        'scheduled',
        'live',
        'final',
        'postponed',
        'cancelled',
        'forfeit'
    )),
    CONSTRAINT ck_matches_distinct_teams CHECK (home_team_id <> away_team_id),
    CONSTRAINT ck_matches_score_paired CHECK (
        (home_score IS NULL AND away_score IS NULL)
        OR (home_score IS NOT NULL AND away_score IS NOT NULL)
    )
);

-- Upsert key: same source feed, same external id, same season+grade.
-- Partial index — only enforce when external_match_id is populated, so
-- manually-created rows (e.g. tests, future scheduled games before the
-- feed has assigned an id) don't collide.
CREATE UNIQUE INDEX IF NOT EXISTS uq_matches_source_external
  ON matches(source, season, grade, external_match_id)
  WHERE external_match_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_matches_season_round_grade
  ON matches(season, round, grade);
CREATE INDEX IF NOT EXISTS idx_matches_kickoff
  ON matches(kickoff_at);
CREATE INDEX IF NOT EXISTS idx_matches_status
  ON matches(status);
CREATE INDEX IF NOT EXISTS idx_matches_home_team
  ON matches(home_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_away_team
  ON matches(away_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_venue
  ON matches(venue_id);

COMMENT ON TABLE matches IS
    'Fixture / result spine — one row per game across all grades '
    '(NRL, NRLW, NSW Cup, QLD Cup, junior pathway). Real-world side of '
    'the model; player_rounds is the SuperCoach overlay that joins to '
    'this via match_id.';

COMMENT ON COLUMN matches.external_match_id IS
    'Upstream feed identifier (e.g. nrl.com matchId). Combined with '
    '`source` to upsert on the daily fixture sync. Nullable so manually '
    'created rows are allowed.';

COMMENT ON COLUMN matches.round IS
    'Numeric round (1..N for regular season). NULL for finals — use '
    '`round_label` for the human form ("Finals Week 1", "Magic Round").';

COMMENT ON COLUMN matches.kickoff_at IS
    'UTC timestamp. Render in venues.tz at display time.';
