"""Integration / drift-detection test for the SuperCoach /settings endpoint.

The unit tests parse the checked-in canonical fixture in CI, so any commit
that changes the top-level envelope model against the fixture is caught
there. This module adds the **live** half of the D8 contract, for both
`classic` and `draft` modes.

Live mode is **env-flagged**: when `MINER_DRIFT_LIVE=1`, the test fetches
the real SuperCoach /settings endpoint and parses the response through the
strict top-level envelope. Run on a schedule against staging or locally
before a release; failures are the user's signal that SuperCoach's
response shape has shifted.

Draft mode is covered here specifically because production cron only ever
refreshes `classic` — this parameterised test is the only guardrail
against silent `draft`-mode breakage.

Per D8 of the Miner charter expansion: the agent does not auto-adapt.
The test fails loudly; the user decides the fix.
"""

from __future__ import annotations

import os
from datetime import date

import pytest
from app.miner.supercoach_settings.fetcher import (
    SuperCoachSettingsFetchError,
    fetch_supercoach_settings,
)
from app.miner.supercoach_settings.models import SuperCoachSettings
from pydantic import ValidationError

LIVE_FLAG = os.environ.get("MINER_DRIFT_LIVE") == "1"


@pytest.mark.skipif(
    not LIVE_FLAG,
    reason="Set MINER_DRIFT_LIVE=1 to run the live-endpoint drift test",
)
@pytest.mark.parametrize("mode", ["classic", "draft"])
def test_live_supercoach_settings_shape(mode):
    """Hit the real SuperCoach /settings endpoint per mode; parse strictly.

    Failure modes:
      - SuperCoachSettingsFetchError: upstream returned an unexpected
        payload (wrong type, unknown mode). Bubbled to the test runner.
      - ValidationError: the top-level envelope failed strict parsing —
        a new or renamed top-level section. This is the drift signal;
        the offending field name is in the error message.
      - HTTP / network errors: same; let pytest surface them.
    """
    try:
        raw = fetch_supercoach_settings(season=date.today().year, mode=mode)
        parsed = SuperCoachSettings.model_validate(raw)
    except (SuperCoachSettingsFetchError, ValidationError) as e:
        pytest.fail(
            f"SuperCoach settings live drift test failed (mode={mode}) — "
            f"upstream shape has changed.\n"
            f"Error: {type(e).__name__}: {e}\n"
            f"Fix path: review the response, update "
            f"app.miner.supercoach_settings.models (top-level envelope only), "
            f"regenerate the fixture, commit with a note on what the upstream "
            f"changed."
        )
    # Sanity gate on a healthy live response
    assert parsed.system["timezone"] == "Australia/Sydney"
    assert len(parsed.game) > 50, f"game dict too small: {len(parsed.game)} keys"
