"""Fetch /ladder/data from nrl.com."""

from __future__ import annotations

from typing import Any

import httpx

LADDER_URL = "https://www.nrl.com/ladder/data"


class NrlcomLadderFetchError(RuntimeError):
    """Raised on unexpected payload."""


def fetch_ladder(
    *,
    competition: int,
    season: int,
    round: int | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    params: dict[str, Any] = {"competition": competition, "season": season}
    if round is not None:
        params["round"] = round
    r = httpx.get(
        LADDER_URL,
        params=params,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        timeout=timeout,
        follow_redirects=True,
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict) or "positions" not in data:
        raise NrlcomLadderFetchError(
            f"Unexpected response: missing 'positions' (keys: {list(data) if isinstance(data, dict) else type(data).__name__})"  # noqa: E501
        )
    return data


__all__ = ["NrlcomLadderFetchError", "fetch_ladder"]
