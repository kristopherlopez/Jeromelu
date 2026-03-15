-- Link sources to channels
ALTER TABLE sources ADD COLUMN channel_id UUID REFERENCES channels(channel_id);
CREATE INDEX idx_sources_channel ON sources(channel_id);

-- Backfill existing sources by matching creator_name to channels.name
UPDATE sources s
SET channel_id = c.channel_id
FROM channels c
WHERE s.creator_name = c.name
  AND s.channel_id IS NULL;
