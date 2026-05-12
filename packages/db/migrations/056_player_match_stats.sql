-- player_match_stats: per-player per-match ~58-field stat line from nrl.com match-centre.
--
-- Populated by the nrlcom_match_centre extractor (downstream of S3 capture
-- per D13). One row per (match, player). nrlcom_player_id is the canonical
-- identity (statspersonform IDs), with person_id as a nullable FK that the
-- extractor populates when name-resolution succeeds against our `people`.
--
-- Rationale for the column list: matches the field names in
-- stats.players.{homeTeam,awayTeam}[] inside nrl.com match-centre. We model
-- every field the upstream returns to satisfy D8 — drift on any column
-- raises in the strict Pydantic extractor.

CREATE TABLE IF NOT EXISTS player_match_stats (
    id                              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    match_id                        UUID REFERENCES matches(match_id) ON DELETE CASCADE,
    nrlcom_match_id                 TEXT NOT NULL,
    nrlcom_player_id                BIGINT NOT NULL,
    person_id                       UUID REFERENCES people(person_id),
    team_id                         UUID REFERENCES teams(team_id),
    nrlcom_team_id                  BIGINT,
    is_home                         BOOLEAN NOT NULL,
    jersey_number                   INTEGER,
    position                        TEXT,
    is_on_field                     BOOLEAN,

    -- Time on field
    minutes_played                  INTEGER,
    stint_one                       INTEGER,

    -- Scoring
    points                          INTEGER,
    tries                           INTEGER,
    try_assists                     INTEGER,
    conversions                     INTEGER,
    conversion_attempts             INTEGER,
    goal_conversion_rate            REAL,
    goals                           INTEGER,
    penalty_goals                   INTEGER,
    field_goals                     INTEGER,
    one_point_field_goals           INTEGER,
    two_point_field_goals           INTEGER,
    fantasy_points_total            INTEGER,

    -- Run / attack
    all_runs                        INTEGER,
    all_run_metres                  INTEGER,
    post_contact_metres             INTEGER,
    hit_ups                         INTEGER,
    hit_up_run_metres               INTEGER,
    dummy_half_runs                 INTEGER,
    dummy_half_run_metres           INTEGER,
    dummy_passes                    INTEGER,
    passes                          INTEGER,
    passes_to_run_ratio             REAL,
    receipts                        INTEGER,
    line_breaks                     INTEGER,
    line_break_assists              INTEGER,
    tackle_breaks                   INTEGER,
    line_engaged_runs               INTEGER,

    -- Kicking
    kicks                           INTEGER,
    kick_metres                     INTEGER,
    kick_return_metres              INTEGER,
    kicks_defused                   INTEGER,
    kicks_dead                      INTEGER,
    bomb_kicks                      INTEGER,
    grubber_kicks                   INTEGER,
    cross_field_kicks               INTEGER,
    forced_drop_out_kicks           INTEGER,
    forty_twenty_kicks              INTEGER,
    twenty_forty_kicks              INTEGER,

    -- Defence
    tackles_made                    INTEGER,
    missed_tackles                  INTEGER,
    ineffective_tackles             INTEGER,
    tackle_efficiency               REAL,
    intercepts                      INTEGER,
    offloads                        INTEGER,
    one_on_one_steal                INTEGER,
    one_on_one_lost                 INTEGER,
    play_the_ball_total             INTEGER,
    play_the_ball_average_speed     REAL,

    -- Discipline
    handling_errors                 INTEGER,
    errors                          INTEGER,
    penalties                       INTEGER,
    ruck_infringements              INTEGER,
    offside_within_ten_metres       INTEGER,
    sin_bins                        INTEGER,
    send_offs                       INTEGER,
    on_report                       INTEGER,

    -- Forensics: the full per-player block as fetched, so any future
    -- column we discover can be derived without re-fetching.
    raw_payload                     JSONB NOT NULL,

    -- S3 source key for traceability
    s3_archive_key                  TEXT,

    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One stat-line per (match, player). Re-runs are idempotent UPSERTs.
CREATE UNIQUE INDEX IF NOT EXISTS uq_player_match_stats_match_player
    ON player_match_stats(nrlcom_match_id, nrlcom_player_id);

CREATE INDEX IF NOT EXISTS idx_player_match_stats_match
    ON player_match_stats(match_id);
CREATE INDEX IF NOT EXISTS idx_player_match_stats_person
    ON player_match_stats(person_id);
CREATE INDEX IF NOT EXISTS idx_player_match_stats_team
    ON player_match_stats(team_id);
