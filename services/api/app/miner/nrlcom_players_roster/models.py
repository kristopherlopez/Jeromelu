"""Strict Pydantic models for the nrl.com /players/data response (D8 drift contract).

The `/players/data?competition=N&team=T` response is a per-team roster: a
single `profileGroups` list (one group per team, observed as title=""), each
group carrying a `profiles[]` list — one entry per player on that team's
top-grade squad. The envelope also carries `filterTeams` — the 17-team
catalogue with the internal nrl.com `team_id` per team — which is the
convenient source TASK-33's `teams.py` derives the walk-set from.

This pipeline ships **no new DB extractor** as part of Phase 4.5 — the
S3-archive is the deliverable; the existing HTML-scrape enrichment in
`jeromelu_shared/players/nrlcom_refresh.py` (which hits per-player profile
PAGES, not this `/players/data` JSON endpoint) is untouched per the scope
decision (2026-05-28 planner interview). Strict modelling therefore stops
at the identity-field level of `Profile` — the `theme` block (club logos /
colours) stays `dict[str, Any] | None` until an extractor lands and reads
into it.

Verified live 2026-05-28 against `competition=111&team=500011` (Broncos —
note: the existing README incorrectly labels 500011 as Storm; the actual
Storm id is 500021, surfaced from this run's `filterTeams[]`). 34 profiles
in a single profileGroup, every profile sharing one 7-key shape:
`bodyImage`, `firstName`, `lastName`, `position`, `teamNickName`, `theme`,
`url`. Envelope: 6 keys (`filterCompetitions`, `filterTeams`, `isClubSite`,
`profileGroups`, `selectedCompetitionId`, `selectedTeamId`).

If the upstream shape changes, the canonical fixture (a real recent
response) drives the test to fail. The agent does not auto-adapt; failure
routes to the user per the Miner charter expansion D8.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class Profile(BaseModel):
    """One player's entry in a profileGroup's `profiles[]` list.

    Every key required-present-but-nullable (the `NrlcomDraw.disclaimer`
    convention) — the key must exist so a rename/removal trips drift; a
    null value is tolerated. `theme` is opaque (club logos / colours, not
    consumed by anything in Phase 4.5).

    `firstName` + `lastName` + `teamNickName` are the load-bearing
    identity fields any future extractor (Person resolution, team
    cross-reference) would read. `position` is the nrl.com canonical
    position label.
    """

    model_config = ConfigDict(extra="forbid")

    firstName: str | None
    lastName: str | None
    teamNickName: str | None
    position: str | None
    url: str | None
    bodyImage: str | None
    theme: dict[str, Any] | None


class ProfileGroup(BaseModel):
    """One group within `profileGroups[]`.

    Observed live as a single group per team with `title=""` (the response
    doesn't sub-group profiles by squad / coaches / staff in the current
    shape — though a `title` discriminator is reserved for that). `profiles`
    is the per-player list.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None
    profiles: list[Profile]


class NrlcomPlayersRoster(BaseModel):
    """Top-level envelope of the nrl.com /players/data response.

    `profileGroups` is the load-bearing payload (the per-team roster).
    `filterTeams` is the 17-team catalogue — TASK-33's `teams.py` derives
    the walk-set from this when refreshing the seed data.
    """

    model_config = ConfigDict(extra="forbid")

    profileGroups: list[ProfileGroup]
    filterCompetitions: list[dict[str, Any]]
    filterTeams: list[dict[str, Any]]
    isClubSite: bool
    selectedCompetitionId: int
    selectedTeamId: int


__all__ = ["NrlcomPlayersRoster", "Profile", "ProfileGroup"]
