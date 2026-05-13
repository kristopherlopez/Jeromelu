-- Relax match_team_lists jersey number constraint.
-- The original 1..30 cap was too tight for COVID-era games and historical
-- emergency call-ups (e.g. 2020-2021 where extended squads carried 32+).
-- Bumping to 1..99 to accommodate observed data without losing the sanity
-- check that excludes obviously bad inputs.

ALTER TABLE match_team_lists DROP CONSTRAINT IF EXISTS ck_match_team_lists_jersey_range;
ALTER TABLE match_team_lists ADD CONSTRAINT ck_match_team_lists_jersey_range
    CHECK (jersey_number IS NULL OR (jersey_number >= 1 AND jersey_number <= 99));
