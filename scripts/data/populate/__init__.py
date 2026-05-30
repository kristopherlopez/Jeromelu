"""S3-to-DB populate phases.

Each module is one extractor that reads from `s3://jeromelu-clean-documents/miner/...`
and projects into DB tables. Run sequentially from the top-level driver
`scripts/data/populate_db_from_s3.py`.

Phases (run in this order to respect FK dependencies):

  1. identity   — backfill people.nrlcom_player_id + teams.nrlcom_team_id
                  from miner/nrlcom/match-centre/ archives
  2. rounds     — extract_rounds from miner/nrlcom/draw/
  3. matches    — extract_matches from miner/nrlcom/match-centre/
  4. team_lists — extract_match_team_lists (incl. coaches as people)
  5. stats      — extract_player_match_stats (59 fields)
  6. timeline   — extract_match_timeline + match_officials
  7. standings  — extract_team_standings from miner/nrlcom/ladder/
  8. leaderboards — extract_stat_leaderboards from miner/nrlcom/stats/
  9. injuries   — extract_injuries state-machine over casualty-ward snapshots
"""
