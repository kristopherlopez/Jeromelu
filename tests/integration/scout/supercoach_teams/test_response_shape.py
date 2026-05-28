"""Integration / drift-detection test for the SuperCoach /teams endpoint.

The unit tests parse the checked-in canonical fixture in CI, so any commit
that changes the models against the fixture is caught there. This module
adds the **live** half of the D8 contract.

Live mode is **env-flagged**: when `SCOUT_DRIFT_LIVE=1`, the test fetches
the real SuperCoach /teams endpoint and parses every team through the
strict models. Run on a schedule against staging or locally before a
release; failures are the user's signal that SuperCoach's response
shape has shifted.

Per D8 of the Scout charter expansion: the agent does not auto-adapt.
The test fails loudly; the user decides the fix.
"""

from __future__ import annotations

import os
from datetime import date

import pytest
from app.scout.supercoach_teams.fetcher import (
    SuperCoachTeamsFetchError,
    fetch_supercoach_teams,
)
from app.scout.supercoach_teams.models import SuperCoachTeam
from pydantic import ValidationError

LIVE_FLAG = os.environ.get("SCOUT_DRIFT_LIVE") == "1"


@pytest.mark.skipif(
    not LIVE_FLAG,
    reason="Set SCOUT_DRIFT_LIVE=1 to run the live-endpoint drift test",
)
def test_live_supercoach_teams_shape():
    """Hit the real SuperCoach /teams endpoint; parse strictly.

    Failure modes:
      - SuperCoachTeamsFetchError: upstream returned an unexpected payload
        (wrong type, off-count team list). Bubbled to the test runner.
      - ValidationError: a team object failed strict parsing. This is
        the drift signal — name + value of the offending field is in
        the error message.
      - HTTP / network errors: same; let pytest surface them.
    """
    try:
        raw = fetch_supercoach_teams(season=date.today().year)
        parsed = [SuperCoachTeam.model_validate(t) for t in raw]
    except (SuperCoachTeamsFetchError, ValidationError) as e:
        pytest.fail(
            f"SuperCoach teams live drift test failed — upstream shape has changed.\n"
            f"Error: {type(e).__name__}: {e}\n"
            f"Fix path: review the response, update "
            f"app.scout.supercoach_teams.models, regenerate the fixture under "
            f"tests/fixtures/scout/supercoach_teams/canonical_response.json, "
            f"commit with a note on what the upstream changed."
        )
    # Sanity gate on a healthy live response
    assert 16 <= len(parsed) <= 18, f"Unexpected team count: {len(parsed)}"
    abbrevs = {t.abbrev for t in parsed}
    assert len(abbrevs) == len(parsed), f"Duplicate abbrevs: {sorted(abbrevs)}"
    assert {t.competition.id for t in parsed} == {2}, "Not all NRL competition (id 2)"
