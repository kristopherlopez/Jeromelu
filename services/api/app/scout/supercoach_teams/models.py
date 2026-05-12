"""Strict Pydantic model for the SuperCoach /teams response (D8 drift contract).

The /teams response is a list of team objects. Each carries identity fields
plus a nested `competition` object. Discovered via live drift test 2026-05-12
that competition is a dict, not an int — corrected the model.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SCCompetition(BaseModel):
    """The competition object nested on each SC team."""

    model_config = ConfigDict(extra="forbid")

    id: int
    season: int | None
    abbrev: str
    name: str
    long_name: str


class SuperCoachTeam(BaseModel):
    """One team in the SC /teams response."""

    model_config = ConfigDict(extra="forbid")

    id: int
    abbrev: str
    feed_name: str
    name: str
    competition: SCCompetition
