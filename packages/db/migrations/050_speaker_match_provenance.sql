-- 050: speaker match provenance + video acquisition fields.
--
-- Phase 4 of speaker-identification. Two distinct concerns folded into
-- one migration because they ship together:
--
--   1. source_speakers gains explicit per-modality match columns so the
--      final `speaker_person_id` can be audited and the Phase 5 review-UI
--      override can show which modality (or both) was responsible:
--
--        audio_match_person_id   - voice-only match (Phase 3 surface)
--        audio_match_score       - max cosine similarity from the winning
--                                  voiceprint window
--        visual_match_person_id  - face-only match (Phase 4 surface)
--        visual_match_score      - max cosine similarity from the winning
--                                  face frame
--        match_method            - 'voice' | 'face' | 'voice+face' |
--                                  'manual' | NULL (not identified)
--        match_confidence        - 0..1, fused confidence used to gate
--                                  whether speaker_person_id was set
--
--      `speaker_person_id` (existing) remains the single fused answer.
--      `confidence` (existing) is left alone — it carried the voice-only
--      max similarity through Phase 3 and Phase 4 will keep writing
--      that for backwards compat. New code reads `match_confidence`.
--
--   2. sources gains video acquisition fields. Scout downloads a
--      low-resolution video stream alongside the audio in Phase 4:
--
--        video_s3_key   - s3://jeromelu-raw-audio/.../<vid>.video.mp4
--        video_format   - 'multi_cam' | 'single_cam' | 'audio_only'
--                         (auto-detected by frame face-change-rate)

BEGIN;

ALTER TABLE source_speakers
    ADD COLUMN audio_match_person_id  UUID REFERENCES people(person_id) ON DELETE SET NULL,
    ADD COLUMN audio_match_score      REAL,
    ADD COLUMN visual_match_person_id UUID REFERENCES people(person_id) ON DELETE SET NULL,
    ADD COLUMN visual_match_score     REAL,
    ADD COLUMN match_method           TEXT,
    ADD COLUMN match_confidence       REAL;

ALTER TABLE source_speakers
    ADD CONSTRAINT ck_source_speakers_match_method
    CHECK (match_method IS NULL
           OR match_method IN ('voice', 'face', 'voice+face', 'manual'));

CREATE INDEX idx_source_speakers_audio_match
    ON source_speakers(audio_match_person_id)
    WHERE audio_match_person_id IS NOT NULL;

CREATE INDEX idx_source_speakers_visual_match
    ON source_speakers(visual_match_person_id)
    WHERE visual_match_person_id IS NOT NULL;

ALTER TABLE sources
    ADD COLUMN video_s3_key TEXT,
    ADD COLUMN video_format TEXT;

ALTER TABLE sources
    ADD CONSTRAINT ck_sources_video_format
    CHECK (video_format IS NULL
           OR video_format IN ('multi_cam', 'single_cam', 'audio_only'));

COMMIT;
