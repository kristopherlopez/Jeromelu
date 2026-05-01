-- 032: player_rounds.match_id, player_rounds.team_id — wire the SC overlay
-- to the new matches / teams spine.
--
-- player_rounds today carries free-text `team` and `opposition` columns,
-- with `venue` also as text. With matches (029) and teams (026) in place
-- we'd like new writes to point at canonical FKs while keeping the
-- existing text columns untouched for back-compat (older ingest history
-- predates the registry tables, and there's no clean way to backfill
-- every row from text alone).
--
-- Strategy:
--   * Add nullable match_id / team_id FKs.
--   * New writes (post-this-migration) populate both.
--   * Old rows stay as-is; a follow-up backfill can fuzzy-match where it
--     can and leave the rest NULL.
--
-- ON DELETE SET NULL on both — losing the FK target shouldn't erase the
-- SC stat row.

ALTER TABLE player_rounds
    ADD COLUMN IF NOT EXISTS match_id UUID
        REFERENCES matches(match_id) ON DELETE SET NULL;

ALTER TABLE player_rounds
    ADD COLUMN IF NOT EXISTS team_id UUID
        REFERENCES teams(team_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_player_rounds_match
  ON player_rounds(match_id)
  WHERE match_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_player_rounds_team
  ON player_rounds(team_id)
  WHERE team_id IS NOT NULL;

COMMENT ON COLUMN player_rounds.match_id IS
    'Canonical match this stat row belongs to. NULL on rows scraped '
    'before migration 032 — the legacy `team`/`opposition`/`venue` text '
    'columns remain populated so historical queries still work.';

COMMENT ON COLUMN player_rounds.team_id IS
    'Canonical team for the player on this round. May lag '
    'player_attributes.team_id when a player is on a feeder grade — '
    'team_id here reflects the actual side fielded that round, not the '
    'parent NRL/NRLW affiliation.';
