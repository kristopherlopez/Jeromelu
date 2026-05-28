"""Integration / drift-detection test for the nrl.com /players/data endpoint.

The unit tests parse the checked-in canonical fixture in CI. This module
adds the **live** half of the D8 contract: when `SCOUT_DRIFT_LIVE=1`, it
fetches the real /players/data endpoint for one team (`team=500011` —
Broncos) and strict-parses it through `NrlcomPlayersRoster`. Run on a
schedule or locally before a release; a failure is the user's signal
that nrl.com's players-data shape has shifted.

Per D8 of the Scout charter expansion: the agent does not auto-adapt.
The test fails loudly; the user decides the fix.
"""

from __future__ import annotations

import os

import pytest
from app.scout.nrlcom_players_roster.fetcher import (
    NrlcomPlayersFetchError,
    fetch_players_roster,
)
from app.scout.nrlcom_players_roster.models import NrlcomPlayersRoster
from pydantic import ValidationError

LIVE_FLAG = os.environ.get("SCOUT_DRIFT_LIVE") == "1"


@pytest.mark.skipif(
    not LIVE_FLAG,
    reason="Set SCOUT_DRIFT_LIVE=1 to run the live-endpoint drift test",
)
def test_live_nrlcom_players_roster_shape():
    """Hit the real nrl.com /players/data endpoint; parse strictly.

    Failure modes:
      - NrlcomPlayersFetchError: upstream returned an unexpected payload.
      - ValidationError: the envelope or a nested level failed strict
        parsing — the drift signal; the offending field name is in the
        error.
      - HTTP / network errors: same; let pytest surface them.
    """
    try:
        # team=500011 = Broncos. Stable per-team-id endpoint; any team's
        # response shape is equivalent (verified live during TASK-31).
        raw = fetch_players_roster(competition=111, team=500011)
        parsed = NrlcomPlayersRoster.model_validate(raw)
    except (NrlcomPlayersFetchError, ValidationError) as e:
        pytest.fail(
            f"nrl.com players-roster live drift test failed — upstream shape has changed.\n"
            f"Error: {type(e).__name__}: {e}\n"
            f"Fix path: review the response, update "
            f"app.scout.nrlcom_players_roster.models, regenerate the fixture under "
            f"tests/fixtures/scout/nrlcom_players_roster/canonical_response.json, "
            f"commit with a note on what the upstream changed."
        )
    # Sanity gate on a healthy live response
    assert len(parsed.profileGroups) >= 1, "Live players-roster returned no profileGroups"
    assert len(parsed.profileGroups[0].profiles) >= 1, "Live players-roster returned no profiles in the first group"
