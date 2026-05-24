"""Strict Pydantic models for the nrl.com /draw/data response (D8 drift contract).

The draw response is a JSON object: a per-round `fixtures` list plus filter
metadata. The pipeline depends on `fixtures[].matchCentreUrl` (the match-centre
walk reads it to discover each match), so both the envelope and each fixture
are modelled strictly (`extra="forbid"`). The nested team / clock /
call-to-action objects are opaque — we don't read their internals at ingest,
but a new fixture-level key, a renamed `matchCentreUrl`, or a new top-level
section trips the drift guard.

If the upstream shape changes, the canonical fixture (a real recent response)
drives the test to fail. The agent does not auto-adapt; failure routes to the
user per the Scout charter expansion D8. Verified against the live endpoint
2026-05-24 (competition 111).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class DrawFixture(BaseModel):
    """One fixture in the /draw/data `fixtures` list.

    `matchCentreUrl` is load-bearing — the match-centre pipeline walks it.
    The team / clock / call-to-action objects are opaque dicts; `extra="forbid"`
    still catches a new or renamed fixture-level key.
    """

    model_config = ConfigDict(extra="forbid")

    matchCentreUrl: str
    homeTeam: dict[str, Any]
    awayTeam: dict[str, Any]
    clock: dict[str, Any]
    callToAction: dict[str, Any] | None
    secondaryCallToAction: dict[str, Any] | None
    isCurrentRound: bool
    matchMode: str
    matchState: str
    roundTitle: str
    type: str
    venue: str
    venueCity: str


class NrlcomDraw(BaseModel):
    """Top-level envelope of the nrl.com /draw/data response."""

    model_config = ConfigDict(extra="forbid")

    fixtures: list[DrawFixture]
    byes: list[dict[str, Any]]
    calendarUrl: str
    disclaimer: str | None
    downloadUrl: str
    filterCompetitions: list[dict[str, Any]]
    filterRounds: list[dict[str, Any]]
    filterSeasons: list[dict[str, Any]]
    filterTeams: list[dict[str, Any]]
    selectedCompetitionId: int
    selectedRoundId: int
    selectedSeasonId: int
    showOdds: bool
    showTeamPositions: bool
