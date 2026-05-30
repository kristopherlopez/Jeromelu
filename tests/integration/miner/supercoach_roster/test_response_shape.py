"""Integration / drift-detection test for the SuperCoach roster endpoint.

Default mode is the same fixture-mode parse that lives in the unit tests
— it runs in CI so any commit that changes the models against the
checked-in fixture is caught.

Live mode is **env-flagged**: when `MINER_DRIFT_LIVE=1`, the test fetches
the real SuperCoach endpoint and parses every response row through the
strict models. Run on a schedule against staging or locally before a
release; failures are the user's signal that SuperCoach's response
shape has shifted.

Per D8 of the Miner charter expansion: the agent does not auto-adapt.
The test fails loudly; the user decides the fix.
"""

from __future__ import annotations

import os

import pytest
from app.miner.supercoach_roster.fetcher import (
    SuperCoachFetchError,
    fetch_strict,
)
from pydantic import ValidationError

LIVE_FLAG = os.environ.get("MINER_DRIFT_LIVE") == "1"


@pytest.mark.skipif(
    not LIVE_FLAG,
    reason="Set MINER_DRIFT_LIVE=1 to run the live-endpoint drift test",
)
def test_live_supercoach_response_shape():
    """Hit the real SuperCoach players-cf endpoint; parse strictly.

    Failure modes:
      - SuperCoachFetchError: upstream returned an unexpected payload
        (too few players, missing teams). Bubbled to the test runner.
      - ValidationError: a player object failed strict parsing. This is
        the drift signal — name + value of the offending field is in
        the error message.
      - HTTP / network errors: same; let pytest surface them.
    """
    try:
        players = fetch_strict()
    except (SuperCoachFetchError, ValidationError) as e:
        pytest.fail(
            f"SuperCoach live drift test failed — upstream shape has changed.\n"
            f"Error: {type(e).__name__}: {e}\n"
            f"Fix path: review the response, update "
            f"app.miner.supercoach_roster.models, regenerate the fixture, "
            f"commit the change with a note on what the upstream changed."
        )
    # Sanity gate on a healthy live response
    assert len(players) >= 400, f"Live response too small: {len(players)} players"
    teams = {p.team.abbrev for p in players}
    assert len(teams) == 17, f"Live response missing teams: got {sorted(teams)}"
