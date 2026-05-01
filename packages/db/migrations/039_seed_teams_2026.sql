-- 039: Seed `teams` with 2026-current rosters across NRL, NRLW, NSW Cup,
-- and Hostplus Cup (QLD Cup), plus the announced 2027/2028 NRL expansion sides.
--
-- Why this is a migration rather than the `make prod-seed-teams` admin path:
-- prod needs the full team set in one shot — the yaml-driven endpoint only
-- expresses one feeder per NRL parent and can't carry standalone Hostplus Cup
-- clubs or expansion-team metadata. This migration is the explicit record of
-- the prod seed; the yaml + admin endpoint stay around for incremental
-- updates (re-running them is a no-op against rows already inserted here).
--
-- Idempotent — every INSERT uses ON CONFLICT (slug) DO UPDATE, so re-running
-- this migration just bumps `updated_at`.
--
-- Skipped intentionally: pathway grades (Jersey Flegg, SG Ball, Mal Meninga,
-- Cyril Connell, Harold Matthews). Schema CHECK allows them but rosters shift
-- per season and need verification against NSWRL.com / QRL.com — populate via
-- a follow-up migration once a downstream consumer needs them.
--
-- Data caveats (verify against current-season sources before tightening):
--   - PNG NRL team (2028 entry): official team name not yet known.
--     Inserted as slug=`papua_new_guinea`, name="Papua New Guinea",
--     metadata_json.name_pending_announcement=true. Update when announced.
--   - Hostplus Cup parent affiliations: only the 5 well-established feeders
--     (Norths Devils, Redcliffe, Burleigh, Sunshine Coast, Townsville) carry
--     parent_team_id. Other 10 clubs are inserted standalone (parent NULL)
--     even though some have informal NRL partnerships — those shift YoY.

BEGIN;

-- ═══════════════════════════════════════════════════════════════════════════
-- Phase 1: NRL — 17 current + 2 expansion = 19
--
-- Perth Bears (2027) and Papua New Guinea (2028) carry their entry year on
-- metadata_json.enters_competition_year so UI/queries can filter "active in
-- season X" until kickoff. `active=true` because they exist as recognised
-- clubs from announcement onward; `active` is a club-status flag, not a
-- "currently playing matches" flag.
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO teams (slug, name, short_name, aliases, grade, competition, parent_team_id, metadata_json, active)
VALUES
  ('brisbane_broncos',            'Brisbane Broncos',                'Broncos',    ARRAY['Bronx'],                     'nrl', 'NRL Premiership', NULL, '{}'::jsonb, true),
  ('canterbury_bulldogs',         'Canterbury-Bankstown Bulldogs',   'Bulldogs',   ARRAY['Dogs','Doggies'],            'nrl', 'NRL Premiership', NULL, '{}'::jsonb, true),
  ('canberra_raiders',            'Canberra Raiders',                'Raiders',    ARRAY['Green Machine'],             'nrl', 'NRL Premiership', NULL, '{}'::jsonb, true),
  ('cronulla_sharks',             'Cronulla-Sutherland Sharks',      'Sharks',     ARRAY['Sharkies'],                  'nrl', 'NRL Premiership', NULL, '{}'::jsonb, true),
  ('dolphins',                    'Dolphins',                        'Dolphins',   ARRAY['Phins'],                     'nrl', 'NRL Premiership', NULL, '{}'::jsonb, true),
  ('gold_coast_titans',           'Gold Coast Titans',               'Titans',     ARRAY['Tits'],                      'nrl', 'NRL Premiership', NULL, '{}'::jsonb, true),
  ('manly_sea_eagles',            'Manly-Warringah Sea Eagles',      'Sea Eagles', ARRAY['Manly','Eagles'],            'nrl', 'NRL Premiership', NULL, '{}'::jsonb, true),
  ('melbourne_storm',             'Melbourne Storm',                 'Storm',      ARRAY['Stormy'],                    'nrl', 'NRL Premiership', NULL, '{}'::jsonb, true),
  ('newcastle_knights',           'Newcastle Knights',               'Knights',    ARRAY['Newy'],                      'nrl', 'NRL Premiership', NULL, '{}'::jsonb, true),
  ('new_zealand_warriors',        'New Zealand Warriors',            'Warriors',   ARRAY['Dubs'],                      'nrl', 'NRL Premiership', NULL, '{}'::jsonb, true),
  ('north_queensland_cowboys',    'North Queensland Cowboys',        'Cowboys',    ARRAY['Cows'],                      'nrl', 'NRL Premiership', NULL, '{}'::jsonb, true),
  ('parramatta_eels',             'Parramatta Eels',                 'Eels',       ARRAY['Parra'],                     'nrl', 'NRL Premiership', NULL, '{}'::jsonb, true),
  ('penrith_panthers',            'Penrith Panthers',                'Panthers',   ARRAY['Penny','Penriff'],           'nrl', 'NRL Premiership', NULL, '{}'::jsonb, true),
  ('south_sydney_rabbitohs',      'South Sydney Rabbitohs',          'Rabbitohs',  ARRAY['Bunnies','Souths','Souffs'], 'nrl', 'NRL Premiership', NULL, '{}'::jsonb, true),
  ('st_george_illawarra_dragons', 'St George Illawarra Dragons',     'Dragons',    ARRAY['Saints','Red V'],            'nrl', 'NRL Premiership', NULL, '{}'::jsonb, true),
  ('sydney_roosters',             'Sydney Roosters',                 'Roosters',   ARRAY['Chooks','Easts'],            'nrl', 'NRL Premiership', NULL, '{}'::jsonb, true),
  ('wests_tigers',                'Wests Tigers',                    'Tigers',     ARRAY['Tigpies','Wests'],           'nrl', 'NRL Premiership', NULL, '{}'::jsonb, true),
  ('perth_bears',                 'Perth Bears',                     'Bears',      ARRAY['Perth'],                     'nrl', 'NRL Premiership', NULL, '{"enters_competition_year": 2027}'::jsonb, true),
  ('papua_new_guinea',            'Papua New Guinea',                'PNG',        ARRAY['PNG'],                       'nrl', 'NRL Premiership', NULL, '{"enters_competition_year": 2028, "name_pending_announcement": true}'::jsonb, true)
ON CONFLICT (slug) DO UPDATE SET
  name          = EXCLUDED.name,
  short_name    = EXCLUDED.short_name,
  aliases       = EXCLUDED.aliases,
  grade         = EXCLUDED.grade,
  competition   = EXCLUDED.competition,
  metadata_json = teams.metadata_json || EXCLUDED.metadata_json,  -- merge, don't overwrite
  updated_at    = now();

-- ═══════════════════════════════════════════════════════════════════════════
-- Phase 2: NRLW — 12, all parented to NRL slug
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO teams (slug, name, short_name, aliases, grade, competition, parent_team_id, active)
SELECT v.slug, v.name, v.short_name, v.aliases, 'nrlw', 'NRLW Premiership', t.team_id, true
FROM (VALUES
  ('brisbane_broncos_nrlw',            'Brisbane Broncos',             'Broncos',  ARRAY['Bronx']::text[], 'brisbane_broncos'),
  ('canberra_raiders_nrlw',            'Canberra Raiders',             'Raiders',  ARRAY[]::text[],        'canberra_raiders'),
  ('canterbury_bulldogs_nrlw',         'Canterbury-Bankstown Bulldogs','Bulldogs', ARRAY[]::text[],        'canterbury_bulldogs'),
  ('cronulla_sharks_nrlw',             'Cronulla-Sutherland Sharks',   'Sharks',   ARRAY[]::text[],        'cronulla_sharks'),
  ('gold_coast_titans_nrlw',           'Gold Coast Titans',            'Titans',   ARRAY[]::text[],        'gold_coast_titans'),
  ('newcastle_knights_nrlw',           'Newcastle Knights',            'Knights',  ARRAY[]::text[],        'newcastle_knights'),
  ('new_zealand_warriors_nrlw',        'New Zealand Warriors',         'Warriors', ARRAY[]::text[],        'new_zealand_warriors'),
  ('north_queensland_cowboys_nrlw',    'North Queensland Cowboys',     'Cowboys',  ARRAY[]::text[],        'north_queensland_cowboys'),
  ('parramatta_eels_nrlw',             'Parramatta Eels',              'Eels',     ARRAY[]::text[],        'parramatta_eels'),
  ('st_george_illawarra_dragons_nrlw', 'St George Illawarra Dragons',  'Dragons',  ARRAY[]::text[],        'st_george_illawarra_dragons'),
  ('sydney_roosters_nrlw',             'Sydney Roosters',              'Roosters', ARRAY[]::text[],        'sydney_roosters'),
  ('wests_tigers_nrlw',                'Wests Tigers',                 'Tigers',   ARRAY[]::text[],        'wests_tigers')
) AS v(slug, name, short_name, aliases, parent_slug)
JOIN teams t ON t.slug = v.parent_slug
ON CONFLICT (slug) DO UPDATE SET
  name           = EXCLUDED.name,
  short_name     = EXCLUDED.short_name,
  aliases        = EXCLUDED.aliases,
  parent_team_id = EXCLUDED.parent_team_id,
  updated_at     = now();

-- ═══════════════════════════════════════════════════════════════════════════
-- Phase 3: NSW Cup — 12, parented to NRL feeder
--
-- Slug convention follows the existing seed: when the reserve-grade name
-- equals the NRL parent name (Knights, Warriors, Eels, Panthers, Dragons,
-- Roosters), we suffix `_nsw_cup` to avoid slug collision. Distinct names
-- (Mounties, Newtown Jets, Blacktown Workers Sea Eagles, North Sydney Bears,
-- Western Suburbs Magpies, Canterbury-Bankstown Bulldogs) get their own slug.
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO teams (slug, name, grade, competition, parent_team_id, active)
SELECT v.slug, v.name, 'nsw_cup', 'NSW Cup', t.team_id, true
FROM (VALUES
  ('canterbury_bankstown_bulldogs',         'Canterbury-Bankstown Bulldogs', 'canterbury_bulldogs'),
  ('mounties',                              'Mounties',                      'canberra_raiders'),
  ('newtown_jets',                          'Newtown Jets',                  'cronulla_sharks'),
  ('blacktown_workers_sea_eagles',          'Blacktown Workers Sea Eagles',  'manly_sea_eagles'),
  ('newcastle_knights_nsw_cup',             'Newcastle Knights',             'newcastle_knights'),
  ('new_zealand_warriors_nsw_cup',          'New Zealand Warriors',          'new_zealand_warriors'),
  ('parramatta_eels_nsw_cup',               'Parramatta Eels',               'parramatta_eels'),
  ('penrith_panthers_nsw_cup',              'Penrith Panthers',              'penrith_panthers'),
  ('north_sydney_bears',                    'North Sydney Bears',            'south_sydney_rabbitohs'),
  ('st_george_illawarra_dragons_nsw_cup',   'St George Illawarra Dragons',   'st_george_illawarra_dragons'),
  ('sydney_roosters_nsw_cup',               'Sydney Roosters',               'sydney_roosters'),
  ('western_suburbs_magpies',               'Western Suburbs Magpies',       'wests_tigers')
) AS v(slug, name, parent_slug)
JOIN teams t ON t.slug = v.parent_slug
ON CONFLICT (slug) DO UPDATE SET
  name           = EXCLUDED.name,
  grade          = EXCLUDED.grade,
  competition    = EXCLUDED.competition,
  parent_team_id = EXCLUDED.parent_team_id,
  updated_at     = now();

-- ═══════════════════════════════════════════════════════════════════════════
-- Phase 4a: Hostplus Cup — 5 NRL-affiliated feeders
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO teams (slug, name, grade, competition, parent_team_id, active)
SELECT v.slug, v.name, 'qld_cup', 'QLD Cup', t.team_id, true
FROM (VALUES
  ('norths_devils',          'Norths Devils',          'brisbane_broncos'),
  ('redcliffe_dolphins',     'Redcliffe Dolphins',     'dolphins'),
  ('burleigh_bears',         'Burleigh Bears',         'gold_coast_titans'),
  ('sunshine_coast_falcons', 'Sunshine Coast Falcons', 'melbourne_storm'),
  ('townsville_blackhawks',  'Townsville Blackhawks',  'north_queensland_cowboys')
) AS v(slug, name, parent_slug)
JOIN teams t ON t.slug = v.parent_slug
ON CONFLICT (slug) DO UPDATE SET
  name           = EXCLUDED.name,
  grade          = EXCLUDED.grade,
  competition    = EXCLUDED.competition,
  parent_team_id = EXCLUDED.parent_team_id,
  updated_at     = now();

-- ═══════════════════════════════════════════════════════════════════════════
-- Phase 4b: Hostplus Cup — 10 standalone clubs (parent NULL pending verification)
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO teams (slug, name, grade, competition, parent_team_id, active)
VALUES
  ('brisbane_tigers',           'Brisbane Tigers',           'qld_cup', 'QLD Cup', NULL, true),
  ('central_queensland_capras', 'Central Queensland Capras', 'qld_cup', 'QLD Cup', NULL, true),
  ('ipswich_jets',              'Ipswich Jets',              'qld_cup', 'QLD Cup', NULL, true),
  ('mackay_cutters',            'Mackay Cutters',            'qld_cup', 'QLD Cup', NULL, true),
  ('northern_pride',            'Northern Pride',            'qld_cup', 'QLD Cup', NULL, true),
  ('png_hunters',               'PNG Hunters',               'qld_cup', 'QLD Cup', NULL, true),
  ('souths_logan_magpies',      'Souths Logan Magpies',      'qld_cup', 'QLD Cup', NULL, true),
  ('tweed_heads_seagulls',      'Tweed Heads Seagulls',      'qld_cup', 'QLD Cup', NULL, true),
  ('western_clydesdales',       'Western Clydesdales',       'qld_cup', 'QLD Cup', NULL, true),
  ('wynnum_manly_seagulls',     'Wynnum Manly Seagulls',     'qld_cup', 'QLD Cup', NULL, true)
ON CONFLICT (slug) DO UPDATE SET
  name        = EXCLUDED.name,
  grade       = EXCLUDED.grade,
  competition = EXCLUDED.competition,
  updated_at  = now();

COMMIT;
