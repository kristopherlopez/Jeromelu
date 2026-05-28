"""Live drift test for the SuperCoach stats endpoint.

Env-flagged (`SCOUT_DRIFT_LIVE=1`). Fetches a small page from the real
nrlsupercoachstats.com jqGrid endpoint, runs the same extract + strict
parse the production endpoint does. Failure means the upstream has
changed — the user decides the fix.
"""

from __future__ import annotations

import os
from datetime import date

import pytest
from app.scout.supercoach_stats.fetcher import (
    SuperCoachStatsFetchError,
    fetch_strict,
)
from pydantic import ValidationError

LIVE_FLAG = os.environ.get("SCOUT_DRIFT_LIVE") == "1"


@pytest.mark.skipif(
    not LIVE_FLAG,
    reason="Set SCOUT_DRIFT_LIVE=1 to run the live-endpoint drift test",
)
def test_live_supercoach_stats_shape():
    """Hit the real jqGrid endpoint for the current season's Totals; strict-parse.

    Uses round=0 (Totals) since that always has data — actual rounds may
    be empty pre-season.
    """
    season = date.today().year
    try:
        players = fetch_strict(season=season, round=0)
    except (SuperCoachStatsFetchError, ValidationError) as e:
        pytest.fail(
            f"SuperCoach stats live drift test failed — upstream shape has changed.\n"
            f"Error: {type(e).__name__}: {e}\n"
            f"Fix path: review the raw response, update either JQGRID_COLUMN_MAP "
            f"(jeromelu_shared.scraping.nrl) or SuperCoachPlayerStats "
            f"(app.scout.supercoach_stats.models), regenerate the fixture, "
            f"commit with a note on what the upstream changed."
        )
    # Sanity gate: pre-season Totals should still have hundreds of rows
    assert len(players) >= 100, f"Live response too small: {len(players)} players"
    teams = {p.team for p in players}
    # Don't assert exactly 17 here — Totals can include retired players from prior seasons
    assert len(teams) >= 10, f"Expected players across many teams, got {sorted(teams)}"
