-- 022: agent_runs rework — one row per run, typed token/cost columns
--
-- Replaces the two-row (started + completed) pattern with a single row keyed
-- by `run_id`, updated in place when the run ends. Promotes per-run token
-- usage and cost rollup from `detail_json` JSONB to typed columns so they're
-- queryable, indexable, and aggregate-friendly without JSONB extraction.
--
-- Drops `round` / `season` (agent-specific concerns; doesn't generalise to
-- non-fantasy agents). Round-aware reporting belongs on the per-agent output
-- tables (e.g. discovered_sources, claims), not on the run-level summary.
--
-- Existing data is disposable test runs — we DROP/TRUNCATE rather than migrate.

DROP TABLE IF EXISTS agent_runs;
TRUNCATE TABLE agent_events;

CREATE TABLE agent_runs (
    run_id                TEXT PRIMARY KEY,
    agent_id              TEXT NOT NULL,
    agent_name            TEXT NOT NULL,

    -- Lifecycle
    status                TEXT NOT NULL DEFAULT 'running',
    started_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at              TIMESTAMPTZ,

    -- Run inputs
    model                 TEXT,
    brief_preview         TEXT,
    bounds_json           JSONB NOT NULL DEFAULT '{}',

    -- Run summary (filled at end)
    summary               TEXT NOT NULL DEFAULT '',
    detail_json           JSONB NOT NULL DEFAULT '{}',
    s3_log_key            TEXT,
    agent_events_count    INTEGER,

    -- Activity totals
    turns_used            INTEGER,
    tool_calls            INTEGER,

    -- Token usage (rolled up from per-turn `agent_events.payload->'usage'`)
    input_tokens          INTEGER,
    output_tokens         INTEGER,
    cache_read_tokens     INTEGER,
    cache_write_tokens    INTEGER,

    -- Cost rollup (USD; estimated, not invoiced)
    token_cost_usd        NUMERIC(12, 6),
    server_tool_cost_usd  NUMERIC(12, 6),
    total_cost_usd        NUMERIC(12, 6),

    CONSTRAINT ck_agent_runs_status
        CHECK (status IN ('running', 'completed', 'aborted', 'failed')),
    CONSTRAINT ck_agent_runs_agent_id
        CHECK (agent_id IN ('scout', 'scribe', 'analyst', 'stats', 'fixtures'))
);

-- "Latest runs by agent" (homepage status, per-agent dashboards)
CREATE INDEX idx_agent_runs_agent_started ON agent_runs (agent_id, started_at DESC);

-- "What's running right now" — partial index keeps it tiny
CREATE INDEX idx_agent_runs_status_running ON agent_runs (started_at DESC)
    WHERE status = 'running';

-- Global timeline
CREATE INDEX idx_agent_runs_started ON agent_runs (started_at DESC);
