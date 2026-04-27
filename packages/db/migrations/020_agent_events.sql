-- 018: agent_events — per-event audit trail for Claude-Agent-SDK-based agents
--
-- One row per event in an agent run. Joined to crew_activity (start + end
-- summary rows) and to agent-specific output tables (e.g. discovered_sources)
-- via run_id. The same events are also serialised to JSONL and uploaded to
-- S3 at run end (long-term forensics) — this table is the live, queryable
-- store while the run is happening and for ad-hoc DB analysis afterwards.
--
-- Standard event types (see jeromelu_shared.agent_audit):
--   run_started, turn_started, text, tool_use, tool_result,
--   server_block, turn_complete, bound_hit, error, run_ended

CREATE TABLE agent_events (
    event_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id      TEXT NOT NULL,
    agent_id    TEXT NOT NULL,
    sequence    INTEGER NOT NULL,           -- 0-indexed, per-run, dense
    t           TIMESTAMPTZ NOT NULL DEFAULT now(),
    type        TEXT NOT NULL,
    turn        INTEGER,                    -- nullable; e.g. run_started has no turn
    payload     JSONB NOT NULL DEFAULT '{}',

    UNIQUE (run_id, sequence)
);

-- Replay one run in order
CREATE INDEX idx_agent_events_run ON agent_events (run_id, sequence);

-- Cross-agent timeline / "what's happening right now"
CREATE INDEX idx_agent_events_agent_t ON agent_events (agent_id, t DESC);

-- Filter by event type (e.g. all tool_use across all runs)
CREATE INDEX idx_agent_events_type ON agent_events (type);
