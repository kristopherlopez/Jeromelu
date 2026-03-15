-- Add precise segment-level timestamps to claims.
-- These point to the exact moment in the transcript where the claim was made,
-- rather than relying on the broader chunk timestamps (~2 min windows).
ALTER TABLE claims ADD COLUMN IF NOT EXISTS start_ts REAL;
ALTER TABLE claims ADD COLUMN IF NOT EXISTS end_ts   REAL;
