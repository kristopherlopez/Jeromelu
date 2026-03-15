-- Player round data from Supercoach API scraping
CREATE TABLE player_rounds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    team TEXT NOT NULL,
    position TEXT NOT NULL,
    round INTEGER NOT NULL,
    season INTEGER NOT NULL,
    score INTEGER,
    price INTEGER,
    breakeven INTEGER,
    minutes INTEGER,
    selected_pct DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_player_round_season UNIQUE (player_id, round, season)
);

CREATE INDEX idx_player_rounds_season_round ON player_rounds(season, round);
CREATE INDEX idx_player_rounds_player ON player_rounds(player_id);
