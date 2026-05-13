-- Rename people_attributes -> player_attributes.
--
-- The table's content (team_id, primary_position, height_cm, weight_kg,
-- contract_until, real_salary_aud, SCD-2 tenure rows) is all
-- player-specific. Coaches/referees/advisors live in `people` but their
-- tenure model is different (people_roles), not this table. Renaming
-- makes the schema self-documenting.
--
-- ALTER TABLE ... RENAME TO updates FK back-references automatically
-- (the internal PG constraint triggers get rebound). We rename the
-- table's own indexes/constraints explicitly so they don't carry the
-- old "people_attributes_*" naming forever.

ALTER TABLE people_attributes RENAME TO player_attributes;

-- Primary key index
ALTER INDEX people_attributes_pkey RENAME TO player_attributes_pkey;

-- Secondary / unique indexes
ALTER INDEX idx_people_attributes_person_current RENAME TO idx_player_attributes_person_current;
ALTER INDEX idx_people_attributes_team_current RENAME TO idx_player_attributes_team_current;
ALTER INDEX uq_people_attributes_current RENAME TO uq_player_attributes_current;
ALTER INDEX uq_people_attributes_nrlcom_tenure RENAME TO uq_player_attributes_nrlcom_tenure;

-- Check constraint
ALTER TABLE player_attributes
    RENAME CONSTRAINT ck_people_attributes_period TO ck_player_attributes_period;

-- Foreign-key constraints (PG keeps the old names through RENAME TABLE)
ALTER TABLE player_attributes
    RENAME CONSTRAINT people_attributes_person_id_fkey TO player_attributes_person_id_fkey;
ALTER TABLE player_attributes
    RENAME CONSTRAINT people_attributes_team_id_fkey TO player_attributes_team_id_fkey;
