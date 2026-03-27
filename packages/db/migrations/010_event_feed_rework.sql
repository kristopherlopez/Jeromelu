-- 010: Rework events table for feed pipeline
-- Add provenance columns and update display_mode to match feed type naming

-- Provenance columns for traceability
ALTER TABLE events
    ADD COLUMN related_claim_ids UUID[] DEFAULT '{}',
    ADD COLUMN related_source_id UUID REFERENCES sources(source_id),
    ADD COLUMN metadata_json JSONB DEFAULT '{}';

CREATE INDEX idx_events_source ON events(related_source_id);

-- Update display_mode values: thought→thinking, system→sys, add watching/signal
ALTER TABLE events DROP CONSTRAINT IF EXISTS ck_display_mode;
ALTER TABLE events ADD CONSTRAINT ck_display_mode
    CHECK (display_mode IN ('watching', 'signal', 'thinking', 'prediction', 'action', 'review', 'sys'));
