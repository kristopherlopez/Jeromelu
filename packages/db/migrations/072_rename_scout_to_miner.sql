-- 072: rename Scout runtime surfaces to Miner
--
-- This is the live schema/data rename. Historical migrations intentionally
-- keep their original Scout names; applying the migration chain to a fresh
-- database reaches the old names first, then this migration moves the active
-- schema to Miner.

BEGIN;

-- Persisted agent ids and the CHECK constraint must move before new Miner
-- runs can be written.
ALTER TABLE agent_runs
    DROP CONSTRAINT IF EXISTS ck_agent_runs_agent_id;

UPDATE agent_runs
SET agent_id = 'miner'
WHERE agent_id = 'scout';

UPDATE agent_runs
SET agent_id = 'presenter_miner'
WHERE agent_id = 'presenter_scout';

UPDATE agent_events
SET agent_id = 'miner'
WHERE agent_id = 'scout';

UPDATE agent_events
SET agent_id = 'presenter_miner'
WHERE agent_id = 'presenter_scout';

ALTER TABLE agent_runs
    ADD CONSTRAINT ck_agent_runs_agent_id
    CHECK (agent_id IN (
        'miner', 'presenter_miner', 'scribe', 'analyst', 'stats', 'fixtures'
    ));

-- Source-discovery candidate inbox.
DO $$
BEGIN
    IF to_regclass('public.scout_candidates') IS NOT NULL
       AND to_regclass('public.miner_candidates') IS NULL THEN
        ALTER TABLE scout_candidates RENAME TO miner_candidates;
    END IF;
END $$;

ALTER INDEX IF EXISTS idx_scout_candidates_status RENAME TO idx_miner_candidates_status;
ALTER INDEX IF EXISTS idx_scout_candidates_kind RENAME TO idx_miner_candidates_kind;
ALTER INDEX IF EXISTS idx_scout_candidates_run RENAME TO idx_miner_candidates_run;
ALTER INDEX IF EXISTS idx_scout_candidates_at RENAME TO idx_miner_candidates_at;

DO $$
BEGIN
    IF to_regclass('public.miner_candidates') IS NOT NULL THEN
        IF EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = 'public.miner_candidates'::regclass
              AND conname = 'ck_scout_candidates_kind'
        ) THEN
            ALTER TABLE miner_candidates
                RENAME CONSTRAINT ck_scout_candidates_kind TO ck_miner_candidates_kind;
        END IF;

        IF EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = 'public.miner_candidates'::regclass
              AND conname = 'ck_scout_candidates_status'
        ) THEN
            ALTER TABLE miner_candidates
                RENAME CONSTRAINT ck_scout_candidates_status TO ck_miner_candidates_status;
        END IF;

        IF EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = 'public.miner_candidates'::regclass
              AND conname = 'uq_scout_candidates_platform_kind_external'
        ) THEN
            ALTER TABLE miner_candidates
                RENAME CONSTRAINT uq_scout_candidates_platform_kind_external
                TO uq_miner_candidates_platform_kind_external;
        END IF;

        COMMENT ON TABLE miner_candidates IS
            'Miner candidate inbox. Miner writes here while finding NRL channels and videos worth onboarding. Humans approve or reject via the admin review queue; approval promotes a row into canonical channels or sources.';
    END IF;
END $$;

-- Presenter-research candidate inbox.
DO $$
BEGIN
    IF to_regclass('public.scout_presenter_candidates') IS NOT NULL
       AND to_regclass('public.miner_presenter_candidates') IS NULL THEN
        ALTER TABLE scout_presenter_candidates RENAME TO miner_presenter_candidates;
    END IF;
END $$;

ALTER INDEX IF EXISTS idx_scout_pres_channel_status RENAME TO idx_miner_pres_channel_status;
ALTER INDEX IF EXISTS uq_scout_pres_channel_name_pending RENAME TO uq_miner_pres_channel_name_pending;

DO $$
BEGIN
    IF to_regclass('public.miner_presenter_candidates') IS NOT NULL THEN
        IF EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = 'public.miner_presenter_candidates'::regclass
              AND conname = 'ck_scout_pres_role'
        ) THEN
            ALTER TABLE miner_presenter_candidates
                RENAME CONSTRAINT ck_scout_pres_role TO ck_miner_pres_role;
        END IF;

        IF EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = 'public.miner_presenter_candidates'::regclass
              AND conname = 'ck_scout_pres_status'
        ) THEN
            ALTER TABLE miner_presenter_candidates
                RENAME CONSTRAINT ck_scout_pres_status TO ck_miner_pres_status;
        END IF;

        COMMENT ON TABLE miner_presenter_candidates IS
            'Presenter Miner staging inbox. The agent files channel presenter candidates here; humans confirm or reject them into source_presenters.';
    END IF;
END $$;

COMMIT;
