"""Strict Pydantic models for the nrl.com /casualty-ward/data response (D8 drift contract).

The casualty-ward response is a JSON object: a `casualties` list (the official
league-wide injury roll) plus filter metadata. Unlike the draw / match-centre
envelopes (whose DB extractors were deferred, so they model only the top level
and keep nested objects opaque), the casualty-ward extractor is **live** —
`scripts/data/populate/phase_aux.py:populate_injuries` reads each casualty's
`firstName`, `lastName`, `teamNickname`, `injury`, `expectedReturn`, and `url`
by exact key. A renamed or removed key there would silently null a column in
`injuries`. So both the envelope **and** the casualty item are modelled
strictly (`extra="forbid"`).

`firstName` / `lastName` / `teamNickname` are required non-null strings (the
extractor's load-bearing identity fields). The remaining keys are
required-present but nullable (declared `T | None` with no default — the key
must exist so a rename/removal trips drift, but a null value won't 500 the
daily cron; same convention as `NrlcomDraw.disclaimer`).

If the upstream shape changes, the canonical fixture (a real recent response)
drives the test to fail. The agent does not auto-adapt; failure routes to the
user per the Miner charter expansion D8. Verified against the live endpoint
2026-05-28 (competition 111, 99 casualties, all sharing one 8-key shape).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class Casualty(BaseModel):
    """One entry in the /casualty-ward/data `casualties` list.

    `firstName` / `lastName` / `teamNickname` are load-bearing — the injuries
    extractor resolves the player and team from them. The `theme` object
    (club logos / colours) is opaque; `extra="forbid"` still catches a new or
    renamed casualty-level key.
    """

    model_config = ConfigDict(extra="forbid")

    firstName: str
    lastName: str
    teamNickname: str
    injury: str | None
    expectedReturn: str | None
    imageUrl: str | None
    url: str | None
    theme: dict[str, Any] | None


class NrlcomCasualtyWard(BaseModel):
    """Top-level envelope of the nrl.com /casualty-ward/data response."""

    model_config = ConfigDict(extra="forbid")

    casualties: list[Casualty]
    filterCompetitions: list[dict[str, Any]]
    filterExpectedReturns: list[dict[str, Any]]
    filterTeams: list[dict[str, Any]]
    selectedCompetitionId: int


__all__ = ["Casualty", "NrlcomCasualtyWard"]
