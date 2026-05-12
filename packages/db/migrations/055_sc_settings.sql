-- Scout supercoach_settings: per-season snapshot of SuperCoach game rules.
--
-- The /api/nrl/classic/v1/settings endpoint returns deeply-nested JSON
-- (competition/content/game/system) with ~100 leaf fields covering lockouts,
-- scoring rules, captains config, dual-position rules, currency, etc.
--
-- Flattening would be high-maintenance and the data isn't queried row-by-row
-- — it's mostly read whole for "explain how SC works" contexts. So we store
-- the whole payload as JSONB, indexed only by (season, captured_at).
--
-- Idempotency: one row per (season, captured_at::date). Same-day re-runs
-- overwrite; first daily snapshot stays as the canonical state for that day.

CREATE TABLE IF NOT EXISTS sc_settings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    season          INTEGER NOT NULL,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    captured_date   DATE GENERATED ALWAYS AS (captured_at::DATE) STORED,
    mode            TEXT NOT NULL DEFAULT 'classic',  -- classic | draft
    payload         JSONB NOT NULL,
    s3_archive_key  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_sc_settings_season_date_mode
    ON sc_settings(season, captured_date, mode);

CREATE INDEX IF NOT EXISTS idx_sc_settings_season
    ON sc_settings(season);
