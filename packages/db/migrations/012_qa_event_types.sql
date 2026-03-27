-- 012: Add question/answer display modes for merged Ask+Feed timeline

ALTER TABLE events DROP CONSTRAINT IF EXISTS ck_display_mode;
ALTER TABLE events ADD CONSTRAINT ck_display_mode
    CHECK (display_mode IN (
        'watching', 'signal', 'thinking', 'prediction', 'action', 'review', 'sys',
        'question', 'answer'
    ));
