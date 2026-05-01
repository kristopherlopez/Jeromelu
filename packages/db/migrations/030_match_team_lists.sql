-- 030: match_team_lists — versioned named-17 announcements per match.
--
-- A team list lifecycle for one game:
--   Tue ~13:00 AEST  → version 1, named 17 + four bench reserves
--   Wed              → potential v2 if a coach reshuffles
--   Thu ~18:00 AEST  → "team list Thursday" — final v3 announcement
--   Match-day        → late changes (in / out, 19th man activation)
--
-- We store every version rather than mutating in place so the historical
-- record is intact — useful for "did the coach change the lineup the
-- night before kickoff?" questions and for SC trade-window analysis.
--
-- Joins:
--   match_id          → matches.match_id   (CASCADE — drop the match,
--                                            drop the announced lists)
--   team_id           → teams.team_id      (RESTRICT)
--   player_entity_id  → entities.entity_id (RESTRICT — must be a known
--                                            player; deleting a player
--                                            mid-season should not silently
--                                            erase their lineup history)

CREATE TABLE IF NOT EXISTS match_team_lists (
    list_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id         UUID NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    team_id          UUID NOT NULL REFERENCES teams(team_id) ON DELETE RESTRICT,
    player_entity_id UUID NOT NULL REFERENCES entities(entity_id) ON DELETE RESTRICT,

    jersey_number    INTEGER,
    named_position   TEXT,
    sc_position      TEXT,

    list_version     INTEGER NOT NULL DEFAULT 1,
    status           TEXT NOT NULL DEFAULT 'named',
    announced_at     TIMESTAMPTZ,
    source           TEXT NOT NULL DEFAULT 'nrl_com',
    metadata_json    JSONB NOT NULL DEFAULT '{}',

    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_match_team_lists_status CHECK (status IN (
        'named',
        'late_change_in',
        'late_change_out',
        '19th_man',
        'reserve',
        'withdrawn'
    )),
    CONSTRAINT ck_match_team_lists_jersey_range CHECK (
        jersey_number IS NULL OR (jersey_number BETWEEN 1 AND 30)
    )
);

-- One row per (match, team, player, version). Enforces "the same player
-- can appear once per announcement", but also lets a player legitimately
-- appear across versions (e.g. v1 reserve → v2 named in 17).
CREATE UNIQUE INDEX IF NOT EXISTS uq_match_team_lists_match_team_player_version
  ON match_team_lists(match_id, team_id, player_entity_id, list_version);

CREATE INDEX IF NOT EXISTS idx_match_team_lists_match
  ON match_team_lists(match_id);
CREATE INDEX IF NOT EXISTS idx_match_team_lists_team
  ON match_team_lists(team_id);
CREATE INDEX IF NOT EXISTS idx_match_team_lists_player
  ON match_team_lists(player_entity_id);

-- Hot read path: "current named 17 for the next Broncos game" —
-- filter on (match_id, team_id) and order by list_version DESC.
CREATE INDEX IF NOT EXISTS idx_match_team_lists_match_team_version
  ON match_team_lists(match_id, team_id, list_version DESC);

COMMENT ON TABLE match_team_lists IS
    'Versioned named-17 announcements per match. Tuesday and Thursday '
    'lists each get a new list_version; late changes append further '
    'versions. Query for the latest version to see the live lineup.';

COMMENT ON COLUMN match_team_lists.named_position IS
    'Position as named on the team list — fullback, wing, centre, '
    'five-eighth, halfback, hooker, prop, second-row, lock, interchange, '
    'reserve. Free-text to absorb minor source spelling differences.';

COMMENT ON COLUMN match_team_lists.sc_position IS
    'SuperCoach position string (HOK, HFB, CTW, FRF, 2RF, MID, FLB, FLX). '
    'Derived from named_position + the player''s SC eligibility — '
    'populated when the SC API is the source, NULL otherwise.';

COMMENT ON COLUMN match_team_lists.list_version IS
    'Monotonically increasing per (match, team). 1 = first public '
    'announcement (Tuesday); higher = later revisions / late changes. '
    'Use list_version DESC for the live current state.';
