"""Fetch /casualty-ward/data from nrl.com."""

from __future__ import annotations

from typing import Any

import httpx


CASUALTY_URL = "https://www.nrl.com/casualty-ward/data"


class NrlcomCasualtyFetchError(RuntimeError):
    """Raised on unexpected payload."""


def fetch_casualty_ward(
    *,
    season: int | None = None,
    competition: int | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """GET /casualty-ward/data. Returns the envelope (casualties + filters)."""
    params: dict[str, Any] = {}
    if season is not None:
        params["season"] = season
    if competition is not None:
        params["competition"] = competition
    r = httpx.get(
        CASUALTY_URL,
        params=params,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        timeout=timeout,
        follow_redirects=True,
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict) or "casualties" not in data:
        raise NrlcomCasualtyFetchError(
            f"Unexpected response: missing 'casualties' (keys: {list(data) if isinstance(data, dict) else type(data).__name__})"
        )
    return data


__all__ = ["fetch_casualty_ward", "NrlcomCasualtyFetchError"]
