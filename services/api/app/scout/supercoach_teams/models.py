"""Strict Pydantic model for the SuperCoach /teams response (D8 drift contract)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SuperCoachTeam(BaseModel):
    """One team in the SC /teams response."""

    model_config = ConfigDict(extra="forbid")

    id: int
    abbrev: str
    feed_name: str
    name: str
    competition: int
