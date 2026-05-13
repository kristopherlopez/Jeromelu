-- Add attendance + ground_conditions to matches.
-- These are present in every modern nrl.com match-centre payload but were
-- not modelled when migration 029 was first written. The extract_matches
-- pipeline reads these fields straight from the L2 archive.

ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS attendance INTEGER,
    ADD COLUMN IF NOT EXISTS ground_conditions TEXT;
