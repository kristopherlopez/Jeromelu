"""Fetch /stats/data from nrl.com."""

from __future__ import annotations

from typing import Any

import httpx

STATS_URL = "https://www.nrl.com/stats/data"


class NrlcomStatsFetchError(RuntimeError):
    """Raised on unexpected payload."""


def fetch_stats(
    *,
    competition: int,
    season: int,
    timeout: float = 30.0,
) -> dict[str, Any]:
    r = httpx.get(
        STATS_URL,
        params={"competition": competition, "season": season},
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        timeout=timeout,
        follow_redirects=True,
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict) or "playerStats" not in data:
        raise NrlcomStatsFetchError(
            f"Unexpected response: missing 'playerStats' (keys: {list(data) if isinstance(data, dict) else type(data).__name__})"  # noqa: E501
        )
    return data


__all__ = ["NrlcomStatsFetchError", "fetch_stats"]
