-- Add a generic metadata_json column to player_rounds.
-- player_rounds already has 60+ typed columns from nrlsupercoachstats. The
-- additional supercoach.com.au overlay (opponent lookahead, projected
-- points, ownership %, MVP value, position ranks) doesn't justify another
-- 20+ named columns. We park it under metadata_json.sc_lookahead and surface
-- specific fields if/when query patterns demand promotion.

ALTER TABLE player_rounds
    ADD COLUMN IF NOT EXISTS metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb;
