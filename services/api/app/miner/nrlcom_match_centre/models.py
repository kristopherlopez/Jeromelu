"""Strict envelope model for the nrl.com match-centre `/data/` response (D8).

The match-centre payload is large (~100-200KB) and deeply nested — lineups,
~58-field per-player stat lines, 100+ timeline events, officials. We do not
model the internals (the ingest pipeline archives the raw payload to S3 as-is;
the DB extractors in Phase 3.5 read it). We model only the **top-level
envelope** with `extra="forbid"` — the guard that catches a new or renamed
top-level section.

The envelope is **match-state-dependent** (verified live 2026-05-24):
- A completed (`FullTime`) match carries result-only sections: `attendance`,
  `officials`, `positionGroups`, `timeline`, `weather`, `groundConditions`,
  `imageUrl`.
- An `Upcoming` match omits those and instead carries `broadcastChannels` and
  `videoProviders`.
So the state-dependent keys are modelled as **optional** (may be absent),
while the 22 keys present in both states are required. `extra="forbid"` still
trips on any key outside this union — the D8 drift signal. The agent does not
auto-adapt; failure routes to the user per the Miner charter expansion D8.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class NrlcomMatchCentre(BaseModel):
    """Top-level envelope of the nrl.com match-centre `/data/` response."""

    model_config = ConfigDict(extra="forbid")

    # --- present in both Upcoming and FullTime (required) ---
    matchId: str  # load-bearing — canonical match id (season+comp+round+game)
    animateMatchClock: bool
    awayTeam: dict[str, Any]
    competition: dict[str, Any]
    gameSeconds: int
    hasExtraTime: bool
    hasOnFieldTracking: bool
    homeTeam: dict[str, Any]
    matchMode: str
    matchState: str
    roundNumber: int
    roundTitle: str
    segmentCount: int
    segmentDuration: int
    showPlayerPositions: bool
    showTeamPositions: bool
    startTime: str
    stats: dict[str, Any]
    updated: str
    url: str
    venue: str
    venueCity: str

    # --- present once the match is played (FullTime); absent for Upcoming ---
    attendance: int | None = None
    officials: list[Any] | None = None
    positionGroups: list[Any] | None = None
    timeline: list[Any] | None = None
    weather: str | None = None
    groundConditions: str | None = None
    imageUrl: str | None = None

    # --- present for Upcoming matches; absent once played ---
    broadcastChannels: list[Any] | None = None
    videoProviders: list[Any] | None = None
