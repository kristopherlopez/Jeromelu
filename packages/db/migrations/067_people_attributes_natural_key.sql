-- Natural-key unique index for the nrlcom-sourced slice of people_attributes.
--
-- SCD-2 tables should never be DELETEd — history is forever. The
-- nrlcom/match-centre reconstruction (phase_attributes) needs to
-- re-run idempotently as match_team_lists grows, so we need a stable
-- natural key it can UPSERT against:
--
--   (person_id, team_id, effective_from)  WHERE source='nrlcom/match-centre'
--
-- This lets phase_attributes do `INSERT ... ON CONFLICT DO UPDATE`
-- which preserves each row's primary-key id (and any downstream FKs)
-- while letting effective_to / is_current / primary_position drift as
-- new appearances are observed.
--
-- The index is intentionally partial: the supercoach-sourced slice has
-- known duplicates (from earlier SC pipeline runs) that are out of
-- scope for this fix. Each pipeline owns its own slice.

CREATE UNIQUE INDEX IF NOT EXISTS uq_people_attributes_nrlcom_tenure
    ON people_attributes (person_id, team_id, effective_from)
    WHERE source = 'nrlcom/match-centre';
