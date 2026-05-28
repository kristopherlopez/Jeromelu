"""Fetch /players/data from nrl.com (per-team)."""

from __future__ import annotations

from typing import Any

import httpx

PLAYERS_URL = "https://www.nrl.com/players/data"


class NrlcomPlayersFetchError(RuntimeError):
    """Raised on unexpected payload."""


def fetch_players_roster(
    *,
    competition: int,
    team: int,
    timeout: float = 20.0,
) -> dict[str, Any]:
    r = httpx.get(
        PLAYERS_URL,
        params={"competition": competition, "team": team},
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        timeout=timeout,
        follow_redirects=True,
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict) or "profileGroups" not in data:
        raise NrlcomPlayersFetchError(
            f"Unexpected response: missing 'profileGroups' (keys: {list(data) if isinstance(data, dict) else type(data).__name__})"  # noqa: E501
        )
    return data


__all__ = ["NrlcomPlayersFetchError", "fetch_players_roster"]
