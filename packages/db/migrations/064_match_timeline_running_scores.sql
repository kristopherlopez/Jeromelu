-- Add running scores to match_timeline events.
-- Scoring events in nrl.com match-centre timeline[] carry `homeScore` and/or
-- `awayScore` (the running total for the side that just scored). Preserving
-- these inline lets "what was the score at X minute" queries answer without
-- replaying the event stream from the start.
--
-- Both columns are nullable since non-scoring events (KICK OFF, GameTime,
-- KickBomb, etc.) don't have a score component.

ALTER TABLE match_timeline
    ADD COLUMN IF NOT EXISTS running_home_score INTEGER,
    ADD COLUMN IF NOT EXISTS running_away_score INTEGER;
