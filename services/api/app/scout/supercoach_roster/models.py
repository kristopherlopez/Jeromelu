"""Strict Pydantic models for the SuperCoach roster response (D8 drift contract).

Strict on the structural envelope — every unknown field on `SuperCoachPlayer`,
`SCTeam`, `SCPosition`, `SCPlayedStatus` raises a `ValidationError`. The
`player_stats` / `odds` / `notes` lists are typed as opaque `list[dict[str,
Any]]` — those are SuperCoach-specific fantasy stat shapes that belong to
Phase 2's `supercoach_stats` pipeline; they change frequently with the game
and are not the roster pipeline's concern.

If SuperCoach adds or renames a field on the structural envelope (e.g. a
new top-level `is_loanee` flag on the player object, or a renamed
`team.abbreviation`), the drift test in
`tests/integration/scout/supercoach_roster/test_response_shape.py` fails
and routes to the user. The agent does not auto-adapt.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class SCTeam(BaseModel):
    """The team object nested on each player."""

    model_config = ConfigDict(extra="forbid")

    id: int
    abbrev: str
    feed_name: str
    name: str


class SCPlayedStatus(BaseModel):
    """Per-player current played status (e.g. {'status': 'pre', 'display': 'Yet to play'})."""

    model_config = ConfigDict(extra="forbid")

    status: str
    display: str


class SCPosition(BaseModel):
    """A position the player is eligible for."""

    model_config = ConfigDict(extra="forbid")

    position: str
    position_long: str
    sort: int


class SuperCoachPlayer(BaseModel):
    """The top-level player envelope from the SuperCoach players-cf endpoint.

    Strict on every field except the three opaque lists noted in the module
    docstring. Drift on any modeled field raises.
    """

    model_config = ConfigDict(extra="forbid")

    id: int
    first_name: str
    last_name: str
    team_id: int
    # "previous_*" fields are null for players with no prior-season history
    # (new arrivals, rookies). Discovered by the D8 live drift test on
    # 2026-05-12 — fixture only had veterans, live response had a rookie.
    previous_games: int | None
    previous_average: float | None
    previous_total: int | None
    feed_id: str
    hs_url: str | None
    injury_suspension_status: str | None
    injury_suspension_status_text: str | None
    locked: bool
    played_status: SCPlayedStatus
    active: bool
    team: SCTeam
    player_stats: list[dict[str, Any]]  # opaque — Phase 2 supercoach_stats
    odds: list[dict[str, Any]]  # opaque — fantasy markets, not roster-relevant
    positions: list[SCPosition]
    notes: list[dict[str, Any]]  # opaque — SC editorial notes
