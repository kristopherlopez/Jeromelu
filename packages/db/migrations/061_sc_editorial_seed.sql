-- Seed the synthetic SuperCoach Editorial entities used to attribute SC notes[]
-- as claims/quotes in the wiki.
--
-- SC's official commentary on players (the `notes[]` array in their
-- players-cf response) is editorial content. Treating it as claims attributed
-- to a synthetic "SuperCoach Editorial" advisor lets the wiki's
-- ## Expert Opinions section pull from SC's own opinions alongside podcast
-- commentary, the Bookkeeper to grade their predictions over time, and the
-- Archivist to surface SC's view on each player.
--
-- The synthetic entities are fixed UUIDs so the extraction logic can
-- reference them deterministically without a lookup.

INSERT INTO people (
    person_id, canonical_name, slug, aliases, metadata_json
)
VALUES (
    'aaaaaaaa-0000-4000-8000-000000000001',
    'SuperCoach Editorial',
    'supercoach-editorial',
    ARRAY['SC Editorial', 'SC Notes']::text[],
    '{"synthetic": true, "role_class": "advisor", "platform": "supercoach.com.au"}'::jsonb
)
ON CONFLICT (slug) DO NOTHING;

INSERT INTO people_roles (
    person_id, role, effective_from, effective_to, is_primary, metadata_json, source
)
SELECT
    'aaaaaaaa-0000-4000-8000-000000000001',
    'advisor',
    DATE '2000-01-01',
    NULL,
    TRUE,
    '{"network": "supercoach.com.au", "kind": "editorial"}'::jsonb,
    'seed/migration-061'
WHERE NOT EXISTS (
    SELECT 1 FROM people_roles
    WHERE person_id = 'aaaaaaaa-0000-4000-8000-000000000001'
);

-- Synthetic source representing all SC editorial commentary
INSERT INTO sources (
    source_id, source_type, title, creator_name, canonical_url,
    approved_flag, ingestion_status, published_at, ingested_at
)
VALUES (
    'aaaaaaaa-0000-4000-8000-000000000002',
    'manual',
    'SuperCoach Editorial Commentary',
    'SuperCoach Editorial',
    'https://www.supercoach.com.au/#editorial-notes',
    TRUE,
    'collected',
    DATE '2000-01-01',
    NOW()
)
ON CONFLICT (canonical_url) DO NOTHING;

-- Synthetic source_document — single row that holds all SC notes as quotes.
-- Each note is one quote attached here with `said_at_reference = note.created_on`.
INSERT INTO source_documents (
    document_id, source_id, raw_text, cleaned_text,
    transcript_available, language, chunk_count
)
VALUES (
    'aaaaaaaa-0000-4000-8000-000000000003',
    'aaaaaaaa-0000-4000-8000-000000000002',
    '',
    '',
    FALSE,
    'en',
    0
)
ON CONFLICT (document_id) DO NOTHING;
