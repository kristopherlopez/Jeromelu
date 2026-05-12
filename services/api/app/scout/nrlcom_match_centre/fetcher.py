"""Fetch per-match data from nrl.com match-centre URLs."""

from __future__ import annotations

import time
from typing import Any

import httpx


class NrlcomMatchCentreFetchError(RuntimeError):
    """Raised on unexpected payload."""


def fetch_match_centre(
    match_centre_url: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """GET the `/data/` suffix on a match-centre URL.

    Accepts either:
      - A full URL: 'https://www.nrl.com/draw/.../round-7/wests-tigers-v-broncos/'
      - A path: '/draw/.../round-7/wests-tigers-v-broncos/'

    Appends 'data/' if not present.
    """
    if match_centre_url.startswith("/"):
        url = f"https://www.nrl.com{match_centre_url}"
    else:
        url = match_centre_url
    if not url.endswith("/"):
        url += "/"
    if not url.endswith("/data/"):
        url += "data/"

    r = httpx.get(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        timeout=timeout,
        follow_redirects=True,
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict) or "matchId" not in data:
        raise NrlcomMatchCentreFetchError(
            f"Unexpected response from {url}: missing matchId "
            f"(keys: {list(data) if isinstance(data, dict) else type(data).__name__})"
        )
    return data


def extract_slug_from_match_centre_url(match_centre_url: str) -> str:
    """'/draw/nrl-premiership/2026/round-7/wests-tigers-v-broncos/' -> 'wests-tigers-v-broncos'."""
    parts = [p for p in match_centre_url.strip("/").split("/") if p]
    return parts[-1] if parts else "unknown"


__all__ = [
    "fetch_match_centre",
    "extract_slug_from_match_centre_url",
    "NrlcomMatchCentreFetchError",
]
