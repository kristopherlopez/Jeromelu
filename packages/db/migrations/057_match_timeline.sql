-- match_timeline: typed play-by-play events per match from nrl.com match-centre.
--
-- Populated by the nrlcom_match_centre extractor. ~100-120 events per match:
-- KICK OFF, Try, Goal, Penalty, KickBomb, LineBreak, Error, SetRestart,
-- RuckInfringement, OffsideWithinTenMetres, LineDropout, CaptainsChallenge,
-- SinBin, SendOff, etc. Each has gameSeconds + teamId + title.

CREATE TABLE IF NOT EXISTS match_timeline (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    match_id            UUID REFERENCES matches(match_id) ON DELETE CASCADE,
    nrlcom_match_id     TEXT NOT NULL,
    sequence            INTEGER NOT NULL,  -- 0..N per match, preserves order
    event_type          TEXT NOT NULL,     -- 'Try', 'Goal', 'SetRestart', 'GameTime', ...
    title               TEXT,              -- 'KICK OFF', 'TRY!' etc.
    game_seconds        INTEGER,           -- seconds since match start (0..4800 for full 80-min game)
    nrlcom_team_id      BIGINT,            -- which team initiated the event (0 for neutral game-state events)
    team_id             UUID REFERENCES teams(team_id),
    -- Some events carry a player; not in the canonical timeline shape but
    -- captured here for events that do reference one (e.g. Try, Goal).
    nrlcom_player_id    BIGINT,
    person_id           UUID REFERENCES people(person_id),
    raw_payload         JSONB NOT NULL,
    s3_archive_key      TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_match_timeline_match_sequence
    ON match_timeline(nrlcom_match_id, sequence);

CREATE INDEX IF NOT EXISTS idx_match_timeline_match
    ON match_timeline(match_id);
CREATE INDEX IF NOT EXISTS idx_match_timeline_type
    ON match_timeline(event_type);
CREATE INDEX IF NOT EXISTS idx_match_timeline_person
    ON match_timeline(person_id) WHERE person_id IS NOT NULL;
