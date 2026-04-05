-- 013: Add crew_activity table for agent activity tracking
--
-- Tracks what each crew agent (Scout, Scribe, Analyst, Stats, Fixtures) does
-- and when. Powers the homepage crew status and round overview page.

CREATE TABLE crew_activity (
    activity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    round INTEGER,
    season INTEGER DEFAULT 2026,
    summary TEXT NOT NULL,
    detail_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_crew_agent_id CHECK (agent_id IN ('scout', 'scribe', 'analyst', 'stats', 'fixtures')),
    CONSTRAINT ck_crew_activity_type CHECK (activity_type IN ('started', 'completed', 'failed', 'handoff'))
);

CREATE INDEX idx_crew_activity_agent ON crew_activity (agent_id);
CREATE INDEX idx_crew_activity_round ON crew_activity (round, season);
CREATE INDEX idx_crew_activity_created ON crew_activity (created_at DESC);
