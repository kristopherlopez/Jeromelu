"""Thin wrapper around the shared SuperCoach fetcher that adds strict Pydantic
parsing (D8 drift contract).

The underlying GET + sanity-bound validation lives in
`jeromelu_shared.players.supercoach.fetch_supercoach_roster`. This wrapper
adds the Scout-layer strictness: every player dict is parsed through
`SuperCoachPlayer` so unknown fields raise.

Returns `list[SuperCoachPlayer]`. Downstream `refresh_roster` accepts the
list as model_dump(); we pass `mode='python'` to keep the dict shape it
expects.
"""

from __future__ import annotations

from typing import Any

from jeromelu_shared.players.supercoach import (
    SuperCoachFetchError,
    fetch_supercoach_roster,
)

from .models import SuperCoachPlayer


def fetch_strict(season: int | None = None, timeout: float = 30.0) -> list[SuperCoachPlayer]:
    """GET the SC roster and parse every entry through strict Pydantic models.

    Raises:
        SuperCoachFetchError: if the upstream payload fails the existing
            shared-package sanity checks (≥400 players, all 17 NRL teams).
        pydantic.ValidationError: if any player object fails strict parsing —
            this is the D8 drift signal. Do not catch this; let it propagate
            so the test / endpoint surfaces it to the user.
    """
    raw: list[dict[str, Any]] = fetch_supercoach_roster(season=season, timeout=timeout)
    return [SuperCoachPlayer.model_validate(p) for p in raw]


__all__ = ["fetch_strict", "SuperCoachFetchError"]
