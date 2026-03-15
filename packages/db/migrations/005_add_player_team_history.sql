-- SCD Type 2 table tracking player-team assignments over time
CREATE TABLE player_team_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_name     TEXT NOT NULL,
    team_key        TEXT NOT NULL,
    team_name       TEXT NOT NULL,
    position        TEXT,
    player_id       INTEGER,
    effective_from  DATE NOT NULL,
    effective_to    DATE,
    is_current      BOOLEAN NOT NULL DEFAULT TRUE,
    source          TEXT NOT NULL DEFAULT 'seed',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_player_team_effective UNIQUE (player_name, effective_from)
);

CREATE INDEX idx_pth_player_current ON player_team_history(player_name, is_current);
CREATE INDEX idx_pth_team_current ON player_team_history(team_key, is_current);
CREATE INDEX idx_pth_player_id ON player_team_history(player_id);
