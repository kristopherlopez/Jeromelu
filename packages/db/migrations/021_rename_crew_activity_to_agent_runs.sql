-- 021: rename crew_activity -> agent_runs with top-level run_id
--
-- Original `crew_activity` table is dropped (data was disposable; only test
-- runs from initial Scout development). New `agent_runs` table is the
-- run-level summary store — start row + end row per agent run, joinable to
-- `agent_events` cleanly via shared `run_id` (now a top-level indexed column
-- instead of buried in JSONB).
--
-- Also TRUNCATEs `agent_events` to clear test data that referenced the now-
-- dropped `crew_activity` rows.

DROP TABLE IF EXISTS crew_activity;

CREATE TABLE agent_runs (
    activity_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id        TEXT,
    agent_id      TEXT NOT NULL,
    agent_name    TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    round         INTEGER,
    season        INTEGER DEFAULT 2026,
    summary       TEXT NOT NULL,
    detail_json   JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_agent_runs_agent_id
        CHECK (agent_id IN ('scout', 'scribe', 'analyst', 'stats', 'fixtures')),
    CONSTRAINT ck_agent_runs_activity_type
        CHECK (activity_type IN ('started', 'completed', 'failed', 'handoff'))
);

CREATE INDEX idx_agent_runs_agent   ON agent_runs (agent_id);
CREATE INDEX idx_agent_runs_run     ON agent_runs (run_id);
CREATE INDEX idx_agent_runs_round   ON agent_runs (round, season);
CREATE INDEX idx_agent_runs_created ON agent_runs (created_at DESC);

-- Wipe agent_events test data so run_ids align with the fresh agent_runs.
TRUNCATE TABLE agent_events;
