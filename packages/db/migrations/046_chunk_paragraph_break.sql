-- 045: Paragraph-break hints on source_chunks.
--
-- Deepgram's prerecorded response includes a `paragraphs` block that groups
-- sentences by pause / speaker change. We render turns by grouping chunks on
-- speaker_segment_id, but a long monologue from one speaker can still benefit
-- from paragraph breaks for readability. Storing a boolean per chunk lets the
-- frontend render breaks without re-reading the raw Deepgram JSON from S3.
--
-- Set at extract time: the first chunk whose start_ts falls inside a Deepgram
-- paragraph is marked paragraph_break=true. The very first chunk of a document
-- is left as false (no preceding paragraph to break from).

BEGIN;

ALTER TABLE source_chunks
    ADD COLUMN paragraph_break BOOLEAN NOT NULL DEFAULT false;

COMMIT;
