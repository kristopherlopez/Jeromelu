-- 031: injuries — append-on-change timeline of player injury / suspension state.
--
-- Two design choices worth calling out:
--
-- 1. Append-on-change, not mutate-in-place. Each daily scrape of the
--    NRL.com casualty ward produces a row only when a player's status
--    has actually changed (or appeared for the first time). That keeps
--    the table small while preserving a faithful timeline you can
--    replay — "what did we know about Hughes' hamstring on the Tuesday
--    of round 9?" stays answerable.
--
-- 2. status is the player's current availability, not the injury type.
--    We carry body_part / mechanism / severity separately so a single
--    row captures both "what is the injury" and "what does it mean for
--    selection". This shape mirrors how casualty wards publish data.
--
-- Joins:
--   player_entity_id → entities.entity_id (CASCADE — if a player is
--                                           deleted, their injury log
--                                           is meaningless anyway)
--   team_id          → teams.team_id      (SET NULL — keep the row even
--                                           if the team is later removed)

CREATE TABLE IF NOT EXISTS injuries (
    injury_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_entity_id     UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    team_id              UUID REFERENCES teams(team_id) ON DELETE SET NULL,

    status                TEXT NOT NULL,
    body_part             TEXT,
    mechanism             TEXT,
    description           TEXT,

    expected_return_round INTEGER,
    expected_return_date  DATE,
    severity              TEXT,

    reported_at           TIMESTAMPTZ NOT NULL,
    resolved_at           TIMESTAMPTZ,

    source                TEXT NOT NULL,
    source_url            TEXT,
    metadata_json         JSONB NOT NULL DEFAULT '{}',

    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_injuries_status CHECK (status IN (
        'training',
        'test',
        '1_week',
        '2_4_weeks',
        '4_8_weeks',
        'indefinite',
        'season',
        'suspended',
        'cleared'
    )),
    CONSTRAINT ck_injuries_severity CHECK (
        severity IS NULL OR severity IN (
            'low',
            'moderate',
            'high',
            'season'
        )
    ),
    CONSTRAINT ck_injuries_mechanism CHECK (
        mechanism IS NULL OR mechanism IN (
            'collision',
            'non_contact',
            'illness',
            'concussion_protocol',
            'suspension',
            'unknown'
        )
    )
);

-- Hot read path: "what's the latest injury status for player X?"
CREATE INDEX IF NOT EXISTS idx_injuries_player_reported
  ON injuries(player_entity_id, reported_at DESC);

-- "Show me Broncos players currently sidelined."
CREATE INDEX IF NOT EXISTS idx_injuries_team_status
  ON injuries(team_id, status)
  WHERE resolved_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_injuries_reported_at
  ON injuries(reported_at);

COMMENT ON TABLE injuries IS
    'Append-on-change timeline of player injury and suspension state. '
    'A new row is written only when status changes; resolving an injury '
    'is recorded with status=cleared and resolved_at set on the prior '
    'open row by the scraper that observes the change.';

COMMENT ON COLUMN injuries.status IS
    'Current availability bucket — mirrors NRL casualty ward labels '
    '(training / test / 1 week / 2-4 weeks / 4-8 weeks / indefinite / '
    'season / suspended / cleared).';

COMMENT ON COLUMN injuries.severity IS
    'Coarse severity bucket independent of status. Optional — populated '
    'when the source is detailed enough (NRL Physio commentary, '
    'post-match medical update). NULL on first observation from a '
    'low-detail casualty ward row.';

COMMENT ON COLUMN injuries.source IS
    'Origin feed: nrl_com_casualty, zerotackle, nrl_physio_twitter, '
    'manual. Used for source-attribution in the wiki and for confidence '
    'weighting downstream.';
