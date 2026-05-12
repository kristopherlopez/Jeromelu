"""Fetch SuperCoach game settings per season."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx


SUPERCOACH_SETTINGS_URL = (
    "https://www.supercoach.com.au/{season}/api/nrl/{mode}/v1/settings"
)


class SuperCoachSettingsFetchError(RuntimeError):
    """Raised on unexpected payload."""


def fetch_supercoach_settings(
    season: int | None = None,
    mode: str = "classic",
    timeout: float = 15.0,
) -> dict[str, Any]:
    """GET the per-season settings JSON. `mode` is 'classic' or 'draft'."""
    if mode not in {"classic", "draft"}:
        raise SuperCoachSettingsFetchError(f"Unknown mode: {mode}")
    season = season or date.today().year
    url = SUPERCOACH_SETTINGS_URL.format(season=season, mode=mode)
    r = httpx.get(url, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise SuperCoachSettingsFetchError(
            f"Unexpected shape: {type(data).__name__}, expected dict"
        )
    return data


__all__ = ["fetch_supercoach_settings", "SuperCoachSettingsFetchError"]
