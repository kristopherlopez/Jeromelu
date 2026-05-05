-- 052: Presenter Scout — staging inbox + confirmed presenter associations
--
-- Adds two tables and one CHECK extension:
--
--   scout_presenter_candidates — staging. The Presenter Scout agent files
--                                here; humans confirm/reject via the admin
--                                review surface.
--
--   source_presenters          — confirmed. (channel_id, person_id, role).
--                                Anchored at channel level — presenters are
--                                a property of the show, not the episode.
--
--   agent_runs.agent_id CHECK  — extended to include 'presenter_scout' so
--                                the new agent's runs can land in agent_runs.
--
-- See docs/todo/source-presenters.md for the full design.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Extend agent_runs.agent_id CHECK to include the new agent
-- ---------------------------------------------------------------------------
ALTER TABLE agent_runs
    DROP CONSTRAINT IF EXISTS ck_agent_runs_agent_id;
ALTER TABLE agent_runs
    ADD CONSTRAINT ck_agent_runs_agent_id
    CHECK (agent_id IN (
        'scout', 'presenter_scout', 'scribe', 'analyst', 'stats', 'fixtures'
    ));

-- ---------------------------------------------------------------------------
-- 2. scout_presenter_candidates — staging inbox
-- ---------------------------------------------------------------------------
CREATE TABLE scout_presenter_candidates (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id          UUID NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,

    name                TEXT NOT NULL,
    role                TEXT NOT NULL,
    evidence_json       JSONB NOT NULL DEFAULT '[]'::jsonb,
    llm_confidence      FLOAT,
    notes               TEXT,
    existing_person_id  UUID REFERENCES people(person_id) ON DELETE SET NULL,

    status              TEXT NOT NULL DEFAULT 'pending',
    reviewed_at         TIMESTAMPTZ,
    reviewed_by         TEXT,
    confirmed_person_id UUID REFERENCES people(person_id) ON DELETE SET NULL,

    run_id              TEXT,
    discovered_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_scout_pres_role
        CHECK (role IN ('host','co-host','regular','frequent-guest')),
    CONSTRAINT ck_scout_pres_status
        CHECK (status IN ('pending','confirmed','rejected'))
);

CREATE INDEX idx_scout_pres_channel_status
    ON scout_presenter_candidates (channel_id, status);

-- Idempotency: re-running the agent on a channel won't double-file a
-- still-pending name. A previously rejected name CAN re-surface (the
-- index is partial on status='pending'), which is intentional.
CREATE UNIQUE INDEX uq_scout_pres_channel_name_pending
    ON scout_presenter_candidates (channel_id, lower(name))
    WHERE status = 'pending';

-- ---------------------------------------------------------------------------
-- 3. source_presenters — confirmed (channel, person) association
-- ---------------------------------------------------------------------------
CREATE TABLE source_presenters (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id    UUID NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
    person_id     UUID NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,

    role          TEXT NOT NULL,
    is_regular    BOOLEAN NOT NULL DEFAULT TRUE,
    since_ts      TIMESTAMPTZ,

    confirmed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_by  TEXT,
    candidate_id  UUID REFERENCES scout_presenter_candidates(id) ON DELETE SET NULL,

    CONSTRAINT ck_src_pres_role
        CHECK (role IN ('host','co-host','regular','frequent-guest')),
    CONSTRAINT uq_src_pres_channel_person UNIQUE (channel_id, person_id)
);

CREATE INDEX idx_src_pres_person ON source_presenters (person_id);

COMMIT;
