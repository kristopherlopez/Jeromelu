"""Fetch the NRL player registry from supercoach.com.au's players-cf endpoint.

The endpoint serves the full top-grade roster unauthenticated, so this is a
single GET — no browser, no OAuth, no interactive 2FA. Safe to run from
cron, from CI, or as the body of an admin endpoint.

Used by:
- ``scripts/data/fetchers/fetch_supercoach_players.py`` — local CLI that
  also regenerates ``data/players.yaml`` for the transcript-cleaning
  pipeline.
- ``POST /api/admin/players/fetch-and-refresh`` — server-side fetch +
  SCD-2 refresh in one call (the production-grade path).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx


SUPERCOACH_BASE = "https://www.supercoach.com.au/{season}/api/nrl/classic/v1/players-cf"
SUPERCOACH_PARAMS: dict[str, Any] = {
    "embed": "notes,odds,player_stats,positions",
    "round": 1,
    "xredir": 1,
}

# Sanity bounds — full top-grade rosters are ~520-560 across the 17 clubs.
MIN_PLAYERS = 400
EXPECTED_NRL_TEAMS = frozenset({
    "BRO", "BUL", "CBR", "SHA", "DOL", "GCT", "MNL", "MEL", "NEW",
    "NQC", "PAR", "PTH", "STH", "STG", "SYD", "NZL", "WST",
})


class SuperCoachFetchError(RuntimeError):
    """Raised when the SC fetch returns an unexpected payload."""


def fetch_supercoach_roster(
    season: int | None = None,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """GET the SC roster and validate it's a sensible top-grade payload.

    Returns the list of player dicts (same shape as
    ``scraped_players_api_raw.json``). Raises ``SuperCoachFetchError`` if
    the response looks truncated or doesn't cover all 17 NRL clubs — in
    which case the caller should NOT pipe the result into
    ``refresh_roster`` (it would mark the missing teams' players for
    transitions on the next run).
    """
    season = season or date.today().year
    url = SUPERCOACH_BASE.format(season=season)
    r = httpx.get(url, params=SUPERCOACH_PARAMS, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise SuperCoachFetchError(
            f"Unexpected response: not a list (got {type(data).__name__})"
        )
    if len(data) < MIN_PLAYERS:
        raise SuperCoachFetchError(
            f"Roster looks truncated: got {len(data)} players, expected >= {MIN_PLAYERS}"
        )
    teams_seen = {(p.get("team") or {}).get("abbrev") for p in data}
    missing = EXPECTED_NRL_TEAMS - teams_seen
    if missing:
        raise SuperCoachFetchError(
            f"Roster missing expected NRL teams: {sorted(missing)}"
        )
    return data
