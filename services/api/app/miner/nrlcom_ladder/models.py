"""Strict Pydantic models for the nrl.com /ladder/data response (D8 drift contract).

The ladder response is a JSON object: a `positions` list (one per team, in
ladder order) plus filter/display metadata. Like casualty-ward — and unlike
draw / match-centre (envelope-only) — the ladder extractor is **live**:
`scripts/data/populate/phase_aux.py:populate_team_standings` reads each
position's `teamNickname`/`movement` and every one of the 22 `stats` metrics
by exact key. A renamed or removed stat key (e.g. `"points for"`) would
silently null a `team_standings` column. So the envelope, the position item,
**and** the stats object are all modelled strictly (`extra="forbid"`).

The 22 stat keys are **space-separated** upstream (`"points for"`,
`"average winning margin"`), which aren't valid Python identifiers, so each is
mapped via `Field(alias=...)` with `populate_by_name=True`. Every field is
required-present-but-nullable (`T | None` with no default — the key must exist
so a rename/removal trips drift, but a null value won't 500 the cron; the
`NrlcomDraw.disclaimer` convention). With `extra="forbid"`, a *new* stat key
also trips. `teamNickname` is required non-null (the extractor's load-bearing
team-resolution field). There is intentionally **no** `position` field — the
upstream response has none; the extractor falls back to the enumerate index
(`pos.get("position") or idx`), and a future upstream `position` key would
correctly trip the envelope guard.

If the upstream shape changes, the canonical fixture (a real recent response)
drives the test to fail. The agent does not auto-adapt; failure routes to the
user per the Miner charter expansion D8. Verified against the live endpoint
2026-05-28 (competition 111, season 2026, 17 positions, one 22-key stats shape).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LadderStats(BaseModel):
    """The 22 per-team metrics under each ladder position's `stats` object.

    Space-separated upstream keys are alias-mapped. Every metric is
    required-present (a removed/renamed key trips drift) but nullable (a null
    value is tolerated). `extra="forbid"` catches a newly-added metric.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    played: int | None
    wins: int | None
    lost: int | None
    drawn: int | None
    byes: int | None
    points: int | None
    points_for: int | None = Field(alias="points for")
    points_against: int | None = Field(alias="points against")
    points_difference: int | None = Field(alias="points difference")
    bonus_points: int | None = Field(alias="bonus points")
    form: str | None
    streak: str | None
    home_record: str | None = Field(alias="home record")
    away_record: str | None = Field(alias="away record")
    day_record: str | None = Field(alias="day record")
    night_record: str | None = Field(alias="night record")
    average_winning_margin: float | None = Field(alias="average winning margin")
    average_losing_margin: float | None = Field(alias="average losing margin")
    close_games: int | None = Field(alias="close games")
    golden_point: int | None = Field(alias="golden point")
    players_used: int | None = Field(alias="players used")
    odds: str | None


class LadderPosition(BaseModel):
    """One team's row in the /ladder/data `positions` list.

    `teamNickname` is load-bearing — the standings extractor resolves the team
    from it. `stats` carries the 22 metrics. `next` (next fixture) and `theme`
    (club logos / colours) are opaque; `extra="forbid"` still catches a new or
    renamed position-level key.
    """

    model_config = ConfigDict(extra="forbid")

    teamNickname: str
    stats: LadderStats
    clubProfileUrl: str | None
    movement: str | None
    next: dict[str, Any] | None
    theme: dict[str, Any] | None


class NrlcomLadder(BaseModel):
    """Top-level envelope of the nrl.com /ladder/data response."""

    model_config = ConfigDict(extra="forbid")

    positions: list[LadderPosition]
    filterCompetitions: list[dict[str, Any]]
    filterRounds: list[dict[str, Any]]
    filterSeasons: list[dict[str, Any]]
    finalistTeams: int
    selectedCompetitionId: int
    selectedRoundId: int
    selectedSeasonId: int
    showBonusPoints: bool
    showOdds: bool
    showPredictor: bool


__all__ = ["LadderPosition", "LadderStats", "NrlcomLadder"]
