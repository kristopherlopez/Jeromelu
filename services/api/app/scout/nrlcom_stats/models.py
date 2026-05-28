"""Strict Pydantic models for the nrl.com /stats/data response (D8 drift contract).

The stats response is a JSON object with two parallel scope blocks —
`playerStats` (player-level leaderboards) and `teamStats` (team-level
leaderboards). Each scope holds a list of categories (`Scoring`, `Attack`,
`Passing`, ...); each category holds a list of subgroups (`Points`, `Tries`,
`Goals`, ...); each subgroup holds a list of `leaders` ranked top-down.

The extractor (`scripts/data/populate/phase_aux.py:populate_stat_leaderboards`)
is **live** and reads nested fields by exact key at every level —
`<scope>Stats[].title`, `groups[].title/statId`, and
`leaders[].firstName/lastName/teamNickName/teamName/playerId/value`. A rename
or removal at any level would silently null a `stat_leaderboards` column.
So the envelope, the category, the subgroup, **and** the leader are all
modelled strictly (`extra="forbid"`) — four levels deep.

Player vs team leader shape (verified live 2026-05-28, competition 111,
season 2026, 182 player leaders + 165 team leaders across 70 subgroups):

- **Universal** leader keys (present on both): `played`, `playerId`, `teamId`,
  `teamName`, `teamNickName`, `theme`, `value`. These are modelled as
  required-present-but-nullable (the `NrlcomDraw.disclaimer` convention) —
  the key must exist so a rename/removal trips drift; a null value won't 500
  the cron.
- **Player-only** keys (absent on team leaders): `firstName`, `lastName`,
  `headImage`, `bodyImage`. These carry a `= None` default so team leaders
  parse cleanly. Trade-off: an upstream removal of e.g. `firstName` from
  player leaders would no longer trip — but `extra="forbid"` still catches
  a *new* leader-level key, and rename/removal of the universal keys still
  trips. This is the same pattern `NrlcomDraw.videoProviders` uses for a
  field added to some fixtures but not others.
- **Sometimes-missing-even-on-player**: `url` (always present on team leaders,
  sometimes absent on player leaders — 2 distinct player keysets observed
  live: with-url and without-url). Also defaulted `= None`.

The `value` field is a `str` upstream (e.g. `"134"`) even for numeric leaders;
the extractor coerces via `float(leader.get("value"))`. Modelled as `str | None`
to match what nrl.com actually returns. `theme` is opaque `dict[str, Any] | None`
(club logos / colours, not read by the extractor).

If the upstream shape changes, the canonical fixture (a real recent response)
drives the test to fail. The agent does not auto-adapt; failure routes to the
user per the Scout charter expansion D8.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class StatLeader(BaseModel):
    """One row in a subgroup's `leaders[]` list.

    Single model covering both player-scope and team-scope leaders. The
    player-only identity fields (`firstName`, `lastName`, `headImage`,
    `bodyImage`) default to `None` so team leaders — which legitimately omit
    them — parse cleanly. `url` also defaults `None` because it's
    sometimes-absent on player leaders. The universal keys remain
    required-present-but-nullable so a rename/removal still trips drift.
    """

    model_config = ConfigDict(extra="forbid")

    # Universal — required-present-but-nullable (the disclaimer convention).
    # A null value is tolerated; the key MUST exist on every leader.
    played: int | None
    playerId: int | None
    teamId: int | None
    teamName: str | None
    teamNickName: str | None
    theme: dict[str, Any] | None
    value: str | None
    # Player-only — the key is absent on team leaders, so a default of None
    # is used (not the required-present convention) per the player-vs-team
    # bifurcation observed live.
    firstName: str | None = None
    lastName: str | None = None
    headImage: str | None = None
    bodyImage: str | None = None
    # Sometimes-missing-even-on-player leaders (always present on team
    # leaders); same `= None` default trade-off.
    url: str | None = None


class StatSubgroup(BaseModel):
    """One subgroup (`Points`, `Tries`, `Goals`, ...) within a category.

    `title` is load-bearing — the extractor reads it for the `subgroup` and
    `stat_title` DB columns. `leaders` is the ranked list.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    statId: int | None
    leaders: list[StatLeader]
    url: str | None


class StatCategory(BaseModel):
    """One category (`Scoring`, `Attack`, `Passing`, ...) within a scope block.

    `title` is load-bearing — the extractor reads it for the `category` DB
    column.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    groups: list[StatSubgroup]


class NrlcomStats(BaseModel):
    """Top-level envelope of the nrl.com /stats/data response.

    Two parallel scope blocks (`playerStats`, `teamStats`) plus filter
    metadata. Verified live 2026-05-28 with 8 categories per scope, 37 + 33
    subgroups total, ~5 leaders per subgroup.
    """

    model_config = ConfigDict(extra="forbid")

    playerStats: list[StatCategory]
    teamStats: list[StatCategory]
    filterCompetitions: list[dict[str, Any]]
    filterSeasons: list[dict[str, Any]]
    selectedCompetitionId: int
    selectedSeasonId: int


__all__ = ["NrlcomStats", "StatCategory", "StatSubgroup", "StatLeader"]
