-- 038: drop entities, entity_roles, player_attributes, polymorphic FK columns
--
-- Phase 3 (destructive) of the entities → typed tables refactor. Phases 1 and 2
-- (mig 036, mig 037, plus the application-code switchover) must be applied
-- before this migration runs.
--
-- This migration:
--   1. Pre-flight verifies that every old-shape FK row has a corresponding
--      new-shape row populated. Aborts the migration if any drift is found.
--   2. Drops polymorphic FK columns from output tables (claims.subject_entity_id,
--      predictions.subject_entity_id / predictor_entity_id, decisions.subject_entity_id,
--      consensus_snapshots.subject_entity_id, knowledge_base.subject_entity_id,
--      wiki_pages.entity_id, quotes.speaker_entity_id, source_speakers.speaker_entity_id,
--      match_team_lists.player_entity_id, injuries.player_entity_id).
--   3. Drops redundant entity_id columns from typed tables (teams, venues, matches).
--   4. Drops the old identity tables (entity_roles, player_attributes, entities).
--   5. Tightens CHECK constraints on single-subject polymorphic tables
--      (wiki_pages exactly-one of typed FKs incl. channel_id; consensus_snapshots
--      exactly-one of typed FKs; knowledge_base at-most-one).
--
-- What this migration deliberately leaves alone:
--   - events.related_entity_ids[] — the events table is deferred from this
--     refactor (separate future redesign). UUIDs in this array become dangling
--     references to a dropped table; accepted until events is rebuilt.
--   - SquadSlot.player_entity_id / SquadTrade.player_*_entity_id — squad tables
--     are planned-not-yet-built but their entity FK columns are dropped here so
--     entities can go. Tables stay (they're planned), but the player references
--     come back as typed FKs when the SuperCoach squad feature is built.

BEGIN;

-- ═════════════════════════════════════════════════════════════════════════════
-- Section 1 — Pre-flight verification: abort if any drift is found
-- ═════════════════════════════════════════════════════════════════════════════

DO $$
DECLARE
    drift_claims      INT;
    drift_predictions INT;
    drift_decisions   INT;
    drift_consensus   INT;
    drift_kb          INT;
    drift_wiki        INT;
    drift_quotes      INT;
    drift_predictor   INT;
    drift_speakers    INT;
    drift_lineups     INT;
    drift_injuries    INT;
BEGIN
    SELECT COUNT(*) INTO drift_claims
    FROM claims c
    WHERE c.subject_entity_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM claim_associations ca
          WHERE ca.claim_id = c.claim_id AND ca.role = 'subject'
      );
    IF drift_claims > 0 THEN
        RAISE EXCEPTION 'claims drift: % rows have subject_entity_id but no claim_associations row', drift_claims;
    END IF;

    SELECT COUNT(*) INTO drift_predictions
    FROM predictions p
    WHERE p.subject_entity_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM prediction_associations pa
          WHERE pa.prediction_id = p.prediction_id AND pa.role = 'subject'
      );
    IF drift_predictions > 0 THEN
        RAISE EXCEPTION 'predictions drift: % rows have subject_entity_id but no prediction_associations row', drift_predictions;
    END IF;

    SELECT COUNT(*) INTO drift_decisions
    FROM decisions d
    WHERE d.subject_entity_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM decision_associations da
          WHERE da.decision_id = d.decision_id AND da.role = 'subject'
      );
    IF drift_decisions > 0 THEN
        RAISE EXCEPTION 'decisions drift: % rows have subject_entity_id but no decision_associations row', drift_decisions;
    END IF;

    SELECT COUNT(*) INTO drift_consensus
    FROM consensus_snapshots s
    WHERE s.subject_entity_id IS NOT NULL
      AND s.person_id IS NULL AND s.team_id IS NULL AND s.match_id IS NULL
      AND s.venue_id IS NULL AND s.round_id IS NULL;
    IF drift_consensus > 0 THEN
        RAISE EXCEPTION 'consensus_snapshots drift: % rows have subject_entity_id but no typed FK', drift_consensus;
    END IF;

    SELECT COUNT(*) INTO drift_kb
    FROM knowledge_base k
    WHERE k.subject_entity_id IS NOT NULL
      AND k.person_id IS NULL AND k.team_id IS NULL AND k.match_id IS NULL
      AND k.venue_id IS NULL AND k.round_id IS NULL;
    IF drift_kb > 0 THEN
        RAISE EXCEPTION 'knowledge_base drift: % rows have subject_entity_id but no typed FK', drift_kb;
    END IF;

    SELECT COUNT(*) INTO drift_wiki
    FROM wiki_pages w
    WHERE w.entity_id IS NOT NULL
      AND w.person_id IS NULL AND w.team_id IS NULL AND w.match_id IS NULL
      AND w.venue_id IS NULL AND w.round_id IS NULL;
    IF drift_wiki > 0 THEN
        RAISE EXCEPTION 'wiki_pages drift: % rows have entity_id but no typed FK', drift_wiki;
    END IF;

    SELECT COUNT(*) INTO drift_quotes
    FROM quotes q
    WHERE q.speaker_entity_id IS NOT NULL AND q.speaker_person_id IS NULL;
    IF drift_quotes > 0 THEN
        RAISE EXCEPTION 'quotes drift: % rows have speaker_entity_id but no speaker_person_id', drift_quotes;
    END IF;

    SELECT COUNT(*) INTO drift_predictor
    FROM predictions p
    WHERE p.predictor_entity_id IS NOT NULL AND p.predictor_person_id IS NULL;
    IF drift_predictor > 0 THEN
        RAISE EXCEPTION 'predictions predictor drift: % rows have predictor_entity_id but no predictor_person_id', drift_predictor;
    END IF;

    SELECT COUNT(*) INTO drift_speakers
    FROM source_speakers s
    WHERE s.speaker_entity_id IS NOT NULL AND s.speaker_person_id IS NULL;
    IF drift_speakers > 0 THEN
        RAISE EXCEPTION 'source_speakers drift: % rows have speaker_entity_id but no speaker_person_id', drift_speakers;
    END IF;

    SELECT COUNT(*) INTO drift_lineups
    FROM match_team_lists m
    WHERE m.player_entity_id IS NOT NULL AND m.player_id IS NULL;
    IF drift_lineups > 0 THEN
        RAISE EXCEPTION 'match_team_lists drift: % rows have player_entity_id but no player_id', drift_lineups;
    END IF;

    SELECT COUNT(*) INTO drift_injuries
    FROM injuries i
    WHERE i.player_entity_id IS NOT NULL AND i.player_id IS NULL;
    IF drift_injuries > 0 THEN
        RAISE EXCEPTION 'injuries drift: % rows have player_entity_id but no player_id', drift_injuries;
    END IF;

    RAISE NOTICE 'Pre-flight verification: no drift detected. Proceeding with destructive migration.';
END $$;

-- ═════════════════════════════════════════════════════════════════════════════
-- Section 2 — Drop polymorphic FK columns from output tables
-- ═════════════════════════════════════════════════════════════════════════════

ALTER TABLE claims              DROP COLUMN IF EXISTS subject_entity_id;
ALTER TABLE predictions         DROP COLUMN IF EXISTS subject_entity_id;
ALTER TABLE predictions         DROP COLUMN IF EXISTS predictor_entity_id;
ALTER TABLE decisions           DROP COLUMN IF EXISTS subject_entity_id;
ALTER TABLE consensus_snapshots DROP COLUMN IF EXISTS subject_entity_id;
ALTER TABLE knowledge_base      DROP COLUMN IF EXISTS subject_entity_id;
ALTER TABLE quotes              DROP COLUMN IF EXISTS speaker_entity_id;
ALTER TABLE source_speakers     DROP COLUMN IF EXISTS speaker_entity_id;
ALTER TABLE match_team_lists    DROP COLUMN IF EXISTS player_entity_id;
ALTER TABLE injuries            DROP COLUMN IF EXISTS player_entity_id;

-- wiki_pages: drop the legacy CHECK first since it references entity_id
ALTER TABLE wiki_pages          DROP CONSTRAINT IF EXISTS ck_wiki_page_subject;
ALTER TABLE wiki_pages          DROP COLUMN IF EXISTS entity_id;

-- ═════════════════════════════════════════════════════════════════════════════
-- Section 3 — Drop redundant entity_id columns from typed tables
-- ═════════════════════════════════════════════════════════════════════════════

ALTER TABLE teams    DROP COLUMN IF EXISTS entity_id;
ALTER TABLE venues   DROP COLUMN IF EXISTS entity_id;
ALTER TABLE matches  DROP COLUMN IF EXISTS entity_id;

-- Squad tables (planned-not-built): drop their entity FK columns so entities
-- can be dropped. Squad tables themselves stay; player FKs return as typed
-- FKs (e.g. player_id → people) when the SuperCoach squad feature is built.
ALTER TABLE squad_slots  DROP COLUMN IF EXISTS player_entity_id;
ALTER TABLE squad_trades DROP COLUMN IF EXISTS player_out_entity_id;
ALTER TABLE squad_trades DROP COLUMN IF EXISTS player_in_entity_id;

-- ═════════════════════════════════════════════════════════════════════════════
-- Section 4 — Drop old identity tables (in dependency order)
-- ═════════════════════════════════════════════════════════════════════════════

-- entity_roles and player_attributes both reference entities; drop them first.
DROP TABLE IF EXISTS entity_roles;
DROP TABLE IF EXISTS player_attributes;
-- Now safe to drop entities itself.
DROP TABLE IF EXISTS entities;

-- ═════════════════════════════════════════════════════════════════════════════
-- Section 5 — Tighten CHECK constraints on single-subject polymorphic tables
-- ═════════════════════════════════════════════════════════════════════════════

-- wiki_pages: exactly-one of typed FKs (incl. channel_id)
ALTER TABLE wiki_pages
    ADD CONSTRAINT ck_wiki_page_subject CHECK (
        (person_id  IS NOT NULL)::int +
        (team_id    IS NOT NULL)::int +
        (match_id   IS NOT NULL)::int +
        (venue_id   IS NOT NULL)::int +
        (round_id   IS NOT NULL)::int +
        (channel_id IS NOT NULL)::int = 1
    );

-- consensus_snapshots: exactly-one of typed FKs (every snapshot has a subject)
ALTER TABLE consensus_snapshots
    ADD CONSTRAINT ck_consensus_snapshots_subject CHECK (
        (person_id IS NOT NULL)::int +
        (team_id   IS NOT NULL)::int +
        (match_id  IS NOT NULL)::int +
        (venue_id  IS NOT NULL)::int +
        (round_id  IS NOT NULL)::int = 1
    );

-- knowledge_base: at-most-one of typed FKs (subject is optional —
-- e.g. round_brief / source_digest / article_* kinds have no subject).
ALTER TABLE knowledge_base
    ADD CONSTRAINT ck_knowledge_base_subject CHECK (
        (person_id IS NOT NULL)::int +
        (team_id   IS NOT NULL)::int +
        (match_id  IS NOT NULL)::int +
        (venue_id  IS NOT NULL)::int +
        (round_id  IS NOT NULL)::int <= 1
    );

COMMIT;

-- ═════════════════════════════════════════════════════════════════════════════
-- Post-migration sanity (run separately)
-- ═════════════════════════════════════════════════════════════════════════════
--
-- SELECT 'people' AS t, COUNT(*) FROM people
-- UNION ALL SELECT 'people_attributes', COUNT(*) FROM people_attributes
-- UNION ALL SELECT 'people_roles',      COUNT(*) FROM people_roles
-- UNION ALL SELECT 'rounds',            COUNT(*) FROM rounds;
--
-- SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='entities') AS entities_exists,
--        EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='entity_roles') AS entity_roles_exists,
--        EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='player_attributes') AS player_attributes_exists;
-- (all three should be FALSE)
