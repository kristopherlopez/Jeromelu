-- match_officials: referees, touch judges, bunker per match from nrl.com.
--
-- The match-centre `officials` array returns 4 entries per match. Each row
-- here is (match, person_or_name, role).

CREATE TABLE IF NOT EXISTS match_officials (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    match_id                UUID REFERENCES matches(match_id) ON DELETE CASCADE,
    nrlcom_match_id         TEXT NOT NULL,
    first_name              TEXT NOT NULL,
    last_name               TEXT NOT NULL,
    role                    TEXT,  -- 'Referee', 'Touch Judge', 'Bunker', etc.
    person_id               UUID REFERENCES people(person_id),  -- nullable; resolved when extractor matches name
    raw_payload             JSONB NOT NULL,
    s3_archive_key          TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One row per (match, official-name) — same official can be in multiple
-- matches; we use the role to differentiate within a match.
CREATE UNIQUE INDEX IF NOT EXISTS uq_match_officials_match_role
    ON match_officials(nrlcom_match_id, first_name, last_name, COALESCE(role, ''));

CREATE INDEX IF NOT EXISTS idx_match_officials_match
    ON match_officials(match_id);
CREATE INDEX IF NOT EXISTS idx_match_officials_person
    ON match_officials(person_id) WHERE person_id IS NOT NULL;
