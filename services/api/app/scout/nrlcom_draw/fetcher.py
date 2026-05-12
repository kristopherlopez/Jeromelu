"""Fetch /draw/data from nrl.com."""

from __future__ import annotations

from typing import Any

import httpx


DRAW_URL = "https://www.nrl.com/draw/data"


class NrlcomDrawFetchError(RuntimeError):
    """Raised on unexpected payload."""


def fetch_draw(
    *,
    competition: int,
    season: int,
    round: int | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """GET /draw/data. Returns the dict envelope (fixtures + filter metadata).

    If `round` is omitted, nrl.com returns the current round.
    """
    params: dict[str, Any] = {"competition": competition, "season": season}
    if round is not None:
        params["round"] = round
    r = httpx.get(
        DRAW_URL,
        params=params,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        timeout=timeout,
        follow_redirects=True,
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict) or "fixtures" not in data:
        raise NrlcomDrawFetchError(
            f"Unexpected response: missing 'fixtures' key (keys: {list(data) if isinstance(data, dict) else type(data).__name__})"
        )
    return data


__all__ = ["fetch_draw", "NrlcomDrawFetchError"]
