-- 037: drop stale CHECK constraints that conflict with their ck_* replacements
--
-- Discovered while running mig 036. Two CHECK constraints exist with
-- postgres-default names that duplicate (and conflict with) the
-- properly-named ck_* constraints declared in models.py:
--
--   claims.claims_claim_type_check    — limits claim_type to old 7 values
--                                       (blocks the new annotation kinds added
--                                       in mig 036's expansion of ck_claim_type).
--   events.events_display_mode_check  — limits display_mode to OLD 5 values
--                                       ('thought', 'system', etc.); blocks
--                                       all the current display_mode values.
--
-- These were created by inline `CHECK (... IN (...))` clauses in mig 001,
-- which postgres named for us. Later migrations added ck_* renamed versions
-- but never dropped the originals. CHECK constraints AND together, so any
-- INSERT now has to pass both — meaning the broader new constraint is
-- effectively useless until the legacy is dropped.
--
-- Other stale-named CHECKs (channels_platform_check, decisions_decision_type_check,
-- sources_source_type_check, events_visibility_check) are LEFT ALONE — they
-- have postgres-default names but they're the only constraint validating those
-- fields (no ck_* replacement). Renaming them is cosmetic; dropping them
-- weakens validation. Out of scope for this migration.

BEGIN;

ALTER TABLE claims  DROP CONSTRAINT IF EXISTS claims_claim_type_check;
ALTER TABLE events  DROP CONSTRAINT IF EXISTS events_display_mode_check;

COMMIT;
