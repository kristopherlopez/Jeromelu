-- 071: matches.data_coverage — era-band marker for the standard-data-model
--
-- Scout Phase 5 lands historical NRL data (1908-2026) into the canonical
-- `matches` table. Pre-2000 match-centre is partial (timeline only); pre-1990
-- has no match-centre at all (draw fixture data only). Per the load-bearing
-- constraint "all the data needs to conform to a standard data model", we keep
-- one row shape across all eras and use NULLs + this marker to record what the
-- source-era could supply.
--
-- Semantic values:
--   'full'              — 2000+: lineups + per-player stats + timeline + officials
--   'lineups+timeline'  — partial (2000s payloads occasionally missing stats, or
--                        pre-finish snapshots of current matches that have lineups
--                        but no stats yet); future-proofing
--   'timeline_only'     — 1990-1999 nrl.com match-centre: timeline section only,
--                        no lineups, no per-player stats
--   'fixture_only'      — 1908-1989 (or anywhere nrl.com match-centre is absent):
--                        draw fixture only — date + teams + result + venue
--
-- Existing matches rows are 2024-2026 match-centre data → default 'full'. The
-- CHECK constraint pins the value space; the partial index keeps the partial
-- coverage rows cheap to skip in downstream queries that want only full matches.

BEGIN;

ALTER TABLE matches
    ADD COLUMN data_coverage text NOT NULL DEFAULT 'full';

ALTER TABLE matches
    ADD CONSTRAINT matches_data_coverage_chk
    CHECK (data_coverage IN ('full', 'lineups+timeline', 'timeline_only', 'fixture_only'));

-- Optional: index the partial-coverage rows so wiki/dashboard queries that
-- only want full-coverage matches can use it. Most queries hit by match_id
-- and don't need this; the index is small and bounded by pre-2000 row count.
CREATE INDEX IF NOT EXISTS idx_matches_data_coverage
    ON matches(data_coverage) WHERE data_coverage <> 'full';

COMMIT;
