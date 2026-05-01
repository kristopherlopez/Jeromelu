-- 042: Refine NRL team aliases — drop redundant/vulgar entries, set the
-- canonical short nickname where applicable. Idempotent.
--
-- Changes:
--   brisbane_broncos      Bronx                       → Broncs
--   new_zealand_warriors  Dubs                        → Wahs
--   gold_coast_titans     Tits                        → (cleared)
--   melbourne_storm       Stormy                      → (cleared)
--   perth_bears           Perth                       → Bears
--   png_chiefs            PNG Chiefs / PNG / Chiefs   → Chiefs

BEGIN;

UPDATE teams SET aliases = ARRAY['Broncs']::text[], updated_at = now() WHERE slug = 'brisbane_broncos';
UPDATE teams SET aliases = ARRAY['Wahs']::text[],   updated_at = now() WHERE slug = 'new_zealand_warriors';
UPDATE teams SET aliases = ARRAY[]::text[],         updated_at = now() WHERE slug = 'gold_coast_titans';
UPDATE teams SET aliases = ARRAY[]::text[],         updated_at = now() WHERE slug = 'melbourne_storm';
UPDATE teams SET aliases = ARRAY['Bears']::text[],  updated_at = now() WHERE slug = 'perth_bears';
UPDATE teams SET aliases = ARRAY['Chiefs']::text[], updated_at = now() WHERE slug = 'png_chiefs';

COMMIT;
