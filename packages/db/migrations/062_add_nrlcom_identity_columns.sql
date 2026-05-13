-- Tier 1 of the post-backfill audit: add nrl.com identity columns so
-- extractors can JOIN on stable IDs instead of fragile name matching.
--
-- nrl.com uses statspersonform-derived integer IDs for players and teams
-- (e.g. playerId=100012669 for Jahream Bula, teamId=500011 for Storm).
-- These IDs appear in every match-centre archive, every per-player
-- match-stat block, every timeline event with a player, and every
-- player profile/casualty entry. Without a column to hold them, the
-- match-centre extractor would have to resolve players by name on
-- every row — slow, fragile, and known-broken for name variants
-- (AJ Brimson ↔ Alexander Brimson, Brad ↔ Bradley Schneider, etc.).
--
-- BIGINT because the values can exceed 2^31 (e.g. 100012669) and the
-- ID space is opaque — we don't know the upper bound.
--
-- UNIQUE so the cross-reference is one-to-one: one nrl.com playerId maps
-- to one of our `people` rows.

ALTER TABLE people
    ADD COLUMN IF NOT EXISTS nrlcom_player_id BIGINT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_people_nrlcom_player_id
    ON people(nrlcom_player_id)
    WHERE nrlcom_player_id IS NOT NULL;

ALTER TABLE teams
    ADD COLUMN IF NOT EXISTS nrlcom_team_id BIGINT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_teams_nrlcom_team_id
    ON teams(nrlcom_team_id)
    WHERE nrlcom_team_id IS NOT NULL;
