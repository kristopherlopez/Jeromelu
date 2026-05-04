-- 045: Split Scout (audio acquisition) from Analyst (transcription).
--
-- Until now `sources.ingestion_status` carried both states — fetch the bytes
-- AND turn them into a transcript. With the audio-first switch (mig 044) the
-- two stages have different owners (Scout vs Analyst), different costs (free
-- vs Deepgram $0.30), and different failure modes. They need independent
-- status fields so a Deepgram failure doesn't roll back Scout's work.
--
-- New shape:
--
--   ingestion_status      ←  Scout's lifecycle
--     'pending'           — discovered, no audio yet
--     'collected'         — audio_s3_key populated, m4a in S3
--     'failed'            — yt-dlp failure, will not retry without manual nudge
--     'completed'         — LEGACY ONLY (auto-caption v1 path), kept to avoid
--                           thrashing 215 prod rows + 2k local dev rows.
--
--   transcription_status  ←  Analyst's lifecycle (NEW)
--     NULL                — not transcribed (Scout still pending or audio not
--                           yet processed)
--     'transcribed'       — Deepgram run, source_documents + source_speakers
--                           + source_chunks rows exist
--     'failed'            — Deepgram error, retry independent of Scout
--
-- The single test source ingested under the combined v1 module is migrated to
-- the new shape: ('collected', 'transcribed'). Legacy auto-caption rows keep
-- ingestion_status='completed' and transcription_status=NULL — they are not
-- transcribed under the canonical path; backfill is a separate effort.

BEGIN;

ALTER TABLE sources
    ADD COLUMN transcription_status TEXT;

ALTER TABLE sources
    ADD CONSTRAINT ck_sources_transcription_status
    CHECK (transcription_status IS NULL
           OR transcription_status IN ('transcribed', 'failed'));

-- Migrate the one source already extracted under the combined module —
-- identified by extraction_method='deepgram_v1'. There is exactly one such
-- row in dev today; in prod (where mig 044 has not yet been applied) this
-- update affects zero rows.
UPDATE sources
   SET ingestion_status = 'collected',
       transcription_status = 'transcribed'
 WHERE extraction_method = 'deepgram_v1';

COMMIT;
