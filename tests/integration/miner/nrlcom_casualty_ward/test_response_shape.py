"""Integration / drift-detection test for the nrl.com /casualty-ward/data endpoint.

The unit tests parse the checked-in canonical fixture in CI. This module
adds the **live** half of the D8 contract: when `MINER_DRIFT_LIVE=1`, it
fetches the real /casualty-ward/data endpoint and strict-parses it through
`NrlcomCasualtyWard`. Run on a schedule or locally before a release; a
failure is the user's signal that nrl.com's casualty-ward shape has shifted.

Per D8 of the Miner charter expansion: the agent does not auto-adapt.
The test fails loudly; the user decides the fix.
"""

from __future__ import annotations

import os

import pytest
from app.miner.nrlcom_casualty_ward.fetcher import (
    NrlcomCasualtyFetchError,
    fetch_casualty_ward,
)
from app.miner.nrlcom_casualty_ward.models import NrlcomCasualtyWard
from pydantic import ValidationError

LIVE_FLAG = os.environ.get("MINER_DRIFT_LIVE") == "1"


@pytest.mark.skipif(
    not LIVE_FLAG,
    reason="Set MINER_DRIFT_LIVE=1 to run the live-endpoint drift test",
)
def test_live_nrlcom_casualty_ward_shape():
    """Hit the real nrl.com /casualty-ward/data endpoint; parse strictly.

    Failure modes:
      - NrlcomCasualtyFetchError: upstream returned an unexpected payload.
      - ValidationError: the envelope or a casualty failed strict parsing —
        the drift signal; the offending field name is in the error.
      - HTTP / network errors: same; let pytest surface them.
    """
    try:
        raw = fetch_casualty_ward(competition=111)
        parsed = NrlcomCasualtyWard.model_validate(raw)
    except (NrlcomCasualtyFetchError, ValidationError) as e:
        pytest.fail(
            f"nrl.com casualty-ward live drift test failed — upstream shape has changed.\n"
            f"Error: {type(e).__name__}: {e}\n"
            f"Fix path: review the response, update "
            f"app.miner.nrlcom_casualty_ward.models, regenerate the fixture under "
            f"tests/fixtures/miner/nrlcom_casualty_ward/canonical_response.json, "
            f"commit with a note on what the upstream changed."
        )
    # Sanity gate on a healthy live response
    assert len(parsed.casualties) >= 1, "Live casualty-ward returned no casualties"
    assert all(c.firstName and c.lastName and c.teamNickname for c in parsed.casualties), (
        "A casualty is missing a load-bearing identity field"
    )
