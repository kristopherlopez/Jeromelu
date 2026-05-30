"""Integration / drift-detection test for the nrl.com /ladder/data endpoint.

The unit tests parse the checked-in canonical fixture in CI. This module
adds the **live** half of the D8 contract: when `MINER_DRIFT_LIVE=1`, it
fetches the real /ladder/data endpoint and strict-parses it through
`NrlcomLadder`. Run on a schedule or locally before a release; a failure is
the user's signal that nrl.com's ladder shape has shifted.

Per D8 of the Miner charter expansion: the agent does not auto-adapt.
The test fails loudly; the user decides the fix.
"""

from __future__ import annotations

import os
from datetime import date

import pytest
from app.miner.nrlcom_ladder.fetcher import NrlcomLadderFetchError, fetch_ladder
from app.miner.nrlcom_ladder.models import NrlcomLadder
from pydantic import ValidationError

LIVE_FLAG = os.environ.get("MINER_DRIFT_LIVE") == "1"


@pytest.mark.skipif(
    not LIVE_FLAG,
    reason="Set MINER_DRIFT_LIVE=1 to run the live-endpoint drift test",
)
def test_live_nrlcom_ladder_shape():
    """Hit the real nrl.com /ladder/data endpoint; parse strictly.

    Failure modes:
      - NrlcomLadderFetchError: upstream returned an unexpected payload.
      - ValidationError: the envelope, a position, or the stats object failed
        strict parsing — the drift signal; the offending field name is in
        the error.
      - HTTP / network errors: same; let pytest surface them.
    """
    try:
        raw = fetch_ladder(competition=111, season=date.today().year)
        parsed = NrlcomLadder.model_validate(raw)
    except (NrlcomLadderFetchError, ValidationError) as e:
        pytest.fail(
            f"nrl.com ladder live drift test failed — upstream shape has changed.\n"
            f"Error: {type(e).__name__}: {e}\n"
            f"Fix path: review the response, update "
            f"app.miner.nrlcom_ladder.models, regenerate the fixture under "
            f"tests/fixtures/miner/nrlcom_ladder/canonical_response.json, "
            f"commit with a note on what the upstream changed."
        )
    # Sanity gate on a healthy live response
    assert len(parsed.positions) >= 1, "Live ladder returned no positions"
    assert all(p.teamNickname for p in parsed.positions), "A position is missing its teamNickname"
