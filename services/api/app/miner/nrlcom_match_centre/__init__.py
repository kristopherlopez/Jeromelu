"""Miner pipeline: nrl.com match-centre (per-match goldmine).

Walks the draw endpoint to discover match URLs, then fetches each
`/data/` suffix for the full per-match record: lineups, ~58-field
per-player stats, 100+ typed timeline events, officials, scoring
narrative, venue/weather/attendance.

Pure capture — DB extraction (match_team_lists, player_match_stats,
match_timeline, match_officials) is downstream per D13.
"""

from .routes import router

__all__ = ["router"]
