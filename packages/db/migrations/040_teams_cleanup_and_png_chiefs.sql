-- 040: Drop home_venue_id / primary_colour / secondary_colour from teams,
-- and rename the PNG NRL placeholder row to its official name.
--
-- Why drop:
--   - home_venue_id: home venue is one-to-many in practice (Magic Round,
--     country-week games, secondary venues), so a single FK on `teams` was an
--     oversimplification. If/when a "primary home venue" pointer is genuinely
--     needed, it can sit in metadata_json or move to a dedicated team_venues
--     join table.
--   - primary_colour / secondary_colour: not currently a first-class concern;
--     downstream features can populate ad-hoc keys in metadata_json without
--     committing the schema to a particular colour shape.
--
-- Why rename PNG:
--   PM Marape announced "PNG Chiefs" on 2025-10-12. Mig 039 used a placeholder
--   slug `papua_new_guinea` with metadata flag `name_pending_announcement`.
--   This row gets the official slug, name, short_name, aliases, and the
--   placeholder flag is cleared.
--
-- Idempotent throughout — re-running is a no-op.

BEGIN;

-- ─── 1. Preserve any data in soon-to-be-dropped columns ──────────────
-- Defensive: copy existing values into metadata_json before the column
-- drops. Local was empty at authoring time but prod may have set values.

UPDATE teams
   SET metadata_json = metadata_json
                       || CASE WHEN primary_colour   IS NOT NULL THEN jsonb_build_object('primary_colour', primary_colour)     ELSE '{}'::jsonb END
                       || CASE WHEN secondary_colour IS NOT NULL THEN jsonb_build_object('secondary_colour', secondary_colour) ELSE '{}'::jsonb END
                       || CASE WHEN home_venue_id    IS NOT NULL THEN jsonb_build_object('home_venue_id', home_venue_id::text) ELSE '{}'::jsonb END,
       updated_at = now()
 WHERE primary_colour IS NOT NULL
    OR secondary_colour IS NOT NULL
    OR home_venue_id IS NOT NULL;

-- ─── 2. Drop the columns ─────────────────────────────────────────────

ALTER TABLE teams DROP COLUMN IF EXISTS home_venue_id;
ALTER TABLE teams DROP COLUMN IF EXISTS primary_colour;
ALTER TABLE teams DROP COLUMN IF EXISTS secondary_colour;

-- ─── 3. Rename PNG row to official name ──────────────────────────────
-- Match either the placeholder slug (DBs that applied mig 039 before this
-- migration was authored) or the new slug with the flag still set (defensive
-- — shouldn't happen, but covers half-applied state).

UPDATE teams
   SET slug          = 'png_chiefs',
       name          = 'Papua New Guinea Chiefs',
       short_name    = 'Chiefs',
       aliases       = ARRAY['PNG Chiefs', 'PNG', 'Chiefs'],
       metadata_json = metadata_json - 'name_pending_announcement',
       updated_at    = now()
 WHERE slug = 'papua_new_guinea'
    OR (slug = 'png_chiefs' AND metadata_json ? 'name_pending_announcement');

COMMIT;
