-- 043: Populate teams.logo_url for the 17 current NRL clubs from NRL.com's
-- /.theme SVG assets. Idempotent.
--
-- URL pattern: https://www.nrl.com/.theme/<club-key>/badge[-light].svg
--   Most clubs use the `badge-light.svg` variant (intended for dark
--   backgrounds); Titans / Eels / Roosters serve their badge at `badge.svg`.
--   `?bust=` cache-buster query strings are deliberately omitted — the
--   underlying file paths are stable across cache rotations.
--
-- Coverage:
--   - 17 current NRL clubs: SVG hotlink to nrl.com.
--   - Perth Bears: JPG hotlink — official SVG badge not yet published at the
--     standard /.theme/bears/ path; using the news-article asset as interim.
--   - PNG Chiefs: NULL — no public badge asset yet (team name announced
--     2025-10-12, logo TBD).
--   - NRLW (12): NULL — UI is expected to fall back to the parent NRL row's
--     logo via parent_team_id. Set explicitly only when NRLW branding diverges.
--   - NSW Cup / Hostplus Cup: NULL — separate research effort against
--     NSWRL / QRL sources.
--
-- v2 upgrade path: download SVGs to our S3 / serve through Caddy and repoint
-- logo_url to our own host. Mitigates breakage if NRL.com restructures /.theme
-- (last brand refresh: 2018).

BEGIN;

-- 17 current NRL clubs
UPDATE teams SET logo_url = 'https://www.nrl.com/.theme/broncos/badge-light.svg',      updated_at = now() WHERE slug = 'brisbane_broncos';
UPDATE teams SET logo_url = 'https://www.nrl.com/.theme/raiders/badge-light.svg',      updated_at = now() WHERE slug = 'canberra_raiders';
UPDATE teams SET logo_url = 'https://www.nrl.com/.theme/bulldogs/badge-light.svg',     updated_at = now() WHERE slug = 'canterbury_bulldogs';
UPDATE teams SET logo_url = 'https://www.nrl.com/.theme/sharks/badge-light.svg',       updated_at = now() WHERE slug = 'cronulla_sharks';
UPDATE teams SET logo_url = 'https://www.nrl.com/.theme/dolphins/badge-light.svg',     updated_at = now() WHERE slug = 'dolphins';
UPDATE teams SET logo_url = 'https://www.nrl.com/.theme/titans/badge.svg',             updated_at = now() WHERE slug = 'gold_coast_titans';
UPDATE teams SET logo_url = 'https://www.nrl.com/.theme/sea-eagles/badge-light.svg',   updated_at = now() WHERE slug = 'manly_sea_eagles';
UPDATE teams SET logo_url = 'https://www.nrl.com/.theme/storm/badge-light.svg',        updated_at = now() WHERE slug = 'melbourne_storm';
UPDATE teams SET logo_url = 'https://www.nrl.com/.theme/knights/badge-light.svg',     updated_at = now() WHERE slug = 'newcastle_knights';
UPDATE teams SET logo_url = 'https://www.nrl.com/.theme/warriors/badge-light.svg',    updated_at = now() WHERE slug = 'new_zealand_warriors';
UPDATE teams SET logo_url = 'https://www.nrl.com/.theme/cowboys/badge-light.svg',     updated_at = now() WHERE slug = 'north_queensland_cowboys';
UPDATE teams SET logo_url = 'https://www.nrl.com/.theme/eels/badge.svg',              updated_at = now() WHERE slug = 'parramatta_eels';
UPDATE teams SET logo_url = 'https://www.nrl.com/.theme/panthers/badge-light.svg',    updated_at = now() WHERE slug = 'penrith_panthers';
UPDATE teams SET logo_url = 'https://www.nrl.com/.theme/rabbitohs/badge-light.svg',   updated_at = now() WHERE slug = 'south_sydney_rabbitohs';
UPDATE teams SET logo_url = 'https://www.nrl.com/.theme/dragons/badge-light.svg',     updated_at = now() WHERE slug = 'st_george_illawarra_dragons';
UPDATE teams SET logo_url = 'https://www.nrl.com/.theme/roosters/badge.svg',          updated_at = now() WHERE slug = 'sydney_roosters';
UPDATE teams SET logo_url = 'https://www.nrl.com/.theme/wests-tigers/badge-light.svg', updated_at = now() WHERE slug = 'wests_tigers';

-- Perth Bears (interim — JPG, no SVG path yet)
UPDATE teams SET logo_url = 'https://www.nrl.com/siteassets/2025/pnginternational/world-cup-qualifiers/perth-bears-logo.jpg', updated_at = now() WHERE slug = 'perth_bears';

-- PNG Chiefs left NULL — flag pending logo publish in metadata.
UPDATE teams
   SET metadata_json = metadata_json || '{"logo_pending_publish": true}'::jsonb,
       updated_at    = now()
 WHERE slug = 'png_chiefs' AND logo_url IS NULL;

COMMIT;
