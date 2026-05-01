-- 028: venues — stadium reference table for fixture / match data.
--
-- Until now, "venue" lived only as a free-text column on player_rounds
-- (e.g. "Suncorp Stadium"). With matches becoming a first-class entity
-- (migration 029) we need a stable reference for capacity, surface,
-- timezone, and city/state metadata.
--
-- Small table — roughly 25–30 NRL/NRLW grounds plus the occasional
-- one-off (Magic Round host city, country trial venues). Slow-changing.
--
-- Seeded from data/venues.yaml via `make seed-venues`. Idempotent.

CREATE TABLE IF NOT EXISTS venues (
    venue_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug          TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    aliases       TEXT[] NOT NULL DEFAULT '{}',
    city          TEXT,
    state         TEXT,
    country       TEXT NOT NULL DEFAULT 'AU',
    capacity      INTEGER,
    surface       TEXT,
    roof          TEXT,
    tz            TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}',
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_venues_surface CHECK (
        surface IS NULL OR surface IN ('grass', 'hybrid', 'synthetic')
    ),
    CONSTRAINT ck_venues_roof CHECK (
        roof IS NULL OR roof IN ('open', 'closed', 'retractable')
    )
);

CREATE INDEX IF NOT EXISTS idx_venues_active ON venues(active);
CREATE INDEX IF NOT EXISTS idx_venues_country_state ON venues(country, state);

COMMENT ON TABLE venues IS
    'Stadium reference — capacity, surface, roof, timezone, location. '
    'Referenced by matches.venue_id. Seeded from data/venues.yaml.';

COMMENT ON COLUMN venues.tz IS
    'IANA timezone for this venue (e.g. Australia/Brisbane). matches.kickoff_at '
    'is stored UTC; render-time conversion uses this column.';

COMMENT ON COLUMN venues.aliases IS
    'Alternative or sponsorship names (e.g. "Lang Park" for Suncorp Stadium, '
    '"AAMI Park" for Melbourne Rectangular). Used for fuzzy matching when '
    'ingesting fixture data from sources that name venues differently.';
