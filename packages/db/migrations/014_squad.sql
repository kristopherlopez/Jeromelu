-- 014: Add squad tables for Jeromelu's team roster and trade history
--
-- squad_slots: Current 17-player roster with position, captain status, rationale
-- squad_trades: Trade history with reasoning linked to decisions

CREATE TABLE squad_slots (
    slot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position TEXT NOT NULL,
    slot_index INTEGER NOT NULL,
    player_entity_id UUID REFERENCES entities(entity_id),
    player_name TEXT NOT NULL,
    is_captain BOOLEAN DEFAULT FALSE,
    is_vice_captain BOOLEAN DEFAULT FALSE,
    rationale TEXT,
    conviction TEXT DEFAULT 'medium',
    added_round INTEGER,
    season INTEGER DEFAULT 2026,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_squad_conviction CHECK (conviction IN ('low', 'medium', 'high')),
    CONSTRAINT ck_squad_position CHECK (position IN ('FLB', 'CTW', '5/8', 'HFB', 'HOK', 'FRF', '2RF', 'FLX'))
);

CREATE UNIQUE INDEX idx_squad_active_slot ON squad_slots (slot_index) WHERE active = TRUE;
CREATE INDEX idx_squad_player ON squad_slots (player_entity_id);
CREATE INDEX idx_squad_season ON squad_slots (season);

CREATE TABLE squad_trades (
    trade_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID REFERENCES decisions(decision_id),
    round INTEGER NOT NULL,
    season INTEGER DEFAULT 2026,
    player_out_entity_id UUID REFERENCES entities(entity_id),
    player_out_name TEXT NOT NULL,
    player_in_entity_id UUID REFERENCES entities(entity_id),
    player_in_name TEXT NOT NULL,
    rationale TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_squad_trades_round ON squad_trades (round, season);
CREATE INDEX idx_squad_trades_created ON squad_trades (created_at DESC);
