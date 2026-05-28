"""Integration / drift-detection test for the nrl.com /draw/data endpoint.

The unit tests parse the checked-in canonical fixture in CI. This module
adds the **live** half of the D8 contract: when `SCOUT_DRIFT_LIVE=1`, it
fetches the real /draw/data endpoint and strict-parses it through
`NrlcomDraw`. Run on a schedule or locally before a release; a failure is
the user's signal that nrl.com's draw shape has shifted.

Per D8 of the Scout charter expansion: the agent does not auto-adapt.
The test fails loudly; the user decides the fix.
"""

from __future__ import annotations

import os
from datetime import date

import pytest
from app.scout.nrlcom_draw.fetcher import NrlcomDrawFetchError, fetch_draw
from app.scout.nrlcom_draw.models import NrlcomDraw
from pydantic import ValidationError

LIVE_FLAG = os.environ.get("SCOUT_DRIFT_LIVE") == "1"


@pytest.mark.skipif(
    not LIVE_FLAG,
    reason="Set SCOUT_DRIFT_LIVE=1 to run the live-endpoint drift test",
)
def test_live_nrlcom_draw_shape():
    """Hit the real nrl.com /draw/data endpoint; parse strictly.

    Failure modes:
      - NrlcomDrawFetchError: upstream returned an unexpected payload.
      - ValidationError: the envelope or a fixture failed strict parsing —
        the drift signal; the offending field name is in the error.
      - HTTP / network errors: same; let pytest surface them.
    """
    try:
        raw = fetch_draw(competition=111, season=date.today().year)
        parsed = NrlcomDraw.model_validate(raw)
    except (NrlcomDrawFetchError, ValidationError) as e:
        pytest.fail(
            f"nrl.com draw live drift test failed — upstream shape has changed.\n"
            f"Error: {type(e).__name__}: {e}\n"
            f"Fix path: review the response, update "
            f"app.scout.nrlcom_draw.models, regenerate the fixture under "
            f"tests/fixtures/scout/nrlcom_draw/canonical_response.json, "
            f"commit with a note on what the upstream changed."
        )
    # Sanity gate on a healthy live response
    assert len(parsed.fixtures) >= 1, "Live draw returned no fixtures"
    assert all(f.matchCentreUrl for f in parsed.fixtures), "A fixture is missing matchCentreUrl"
