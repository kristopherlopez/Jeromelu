"""Integration / drift-detection test for the nrl.com match-centre endpoint.

The unit tests parse the checked-in canonical fixtures (FullTime + Upcoming)
in CI. This module adds the **live** half of the D8 contract: when
`SCOUT_DRIFT_LIVE=1`, it resolves a real match from the current draw and
strict-parses its match-centre payload through `NrlcomMatchCentre`. Run on a
schedule or locally before a release; a failure is the user's signal that
nrl.com's match-centre shape has shifted.

Per D8 of the Scout charter expansion: the agent does not auto-adapt.
The test fails loudly; the user decides the fix.
"""

from __future__ import annotations

import os
from datetime import date

import pytest
from app.scout.nrlcom_draw.fetcher import NrlcomDrawFetchError, fetch_draw
from app.scout.nrlcom_match_centre.fetcher import (
    NrlcomMatchCentreFetchError,
    fetch_match_centre,
)
from app.scout.nrlcom_match_centre.models import NrlcomMatchCentre
from pydantic import ValidationError

LIVE_FLAG = os.environ.get("SCOUT_DRIFT_LIVE") == "1"


@pytest.mark.skipif(
    not LIVE_FLAG,
    reason="Set SCOUT_DRIFT_LIVE=1 to run the live-endpoint drift test",
)
def test_live_nrlcom_match_centre_shape():
    """Hit a real nrl.com match-centre endpoint; parse the envelope strictly.

    Resolves the first fixture of the current round from the draw, fetches its
    match-centre payload, and validates the top-level envelope.

    Failure modes:
      - NrlcomDrawFetchError / NrlcomMatchCentreFetchError: upstream returned
        an unexpected payload.
      - ValidationError: the envelope failed strict parsing — the drift signal;
        the offending top-level field is in the error message.
      - HTTP / network errors: same; let pytest surface them.
    """
    try:
        draw = fetch_draw(competition=111, season=date.today().year)
        fixtures = draw.get("fixtures", [])
        assert fixtures, "Live draw returned no fixtures to resolve a match from"
        mc_url = fixtures[0]["matchCentreUrl"]
        raw = fetch_match_centre(mc_url)
        parsed = NrlcomMatchCentre.model_validate(raw)
    except (NrlcomMatchCentreFetchError, NrlcomDrawFetchError, ValidationError) as e:
        pytest.fail(
            f"nrl.com match-centre live drift test failed — upstream shape has changed.\n"
            f"Error: {type(e).__name__}: {e}\n"
            f"Fix path: review the response, update "
            f"app.scout.nrlcom_match_centre.models (top-level envelope only — note the "
            f"FullTime/Upcoming state split), regenerate the fixtures under "
            f"tests/fixtures/scout/nrlcom_match_centre/, commit with a note on what "
            f"the upstream changed."
        )
    # Sanity gate on a healthy live response
    assert parsed.matchId, "match-centre response missing matchId"
