"""Fetch the SuperCoach team registry from the official endpoint."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx


SUPERCOACH_TEAMS_URL = (
    "https://www.supercoach.com.au/{season}/api/nrl/classic/v1/teams"
)


class SuperCoachTeamsFetchError(RuntimeError):
    """Raised when the SC teams fetch returns an unexpected payload."""


def fetch_supercoach_teams(
    season: int | None = None,
    timeout: float = 15.0,
) -> list[dict[str, Any]]:
    """GET the 17-team registry.

    Validates the response is a list with 17 entries (the NRL competition size).
    Raises SuperCoachTeamsFetchError if the shape is unexpected.
    """
    season = season or date.today().year
    url = SUPERCOACH_TEAMS_URL.format(season=season)
    r = httpx.get(url, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise SuperCoachTeamsFetchError(
            f"Unexpected response shape: {type(data).__name__}, expected list"
        )
    if len(data) < 16 or len(data) > 18:
        raise SuperCoachTeamsFetchError(
            f"Unexpected team count: {len(data)} (NRL has 17)"
        )
    return data


__all__ = ["fetch_supercoach_teams", "SuperCoachTeamsFetchError"]
