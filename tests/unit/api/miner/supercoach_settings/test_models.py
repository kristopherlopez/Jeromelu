"""Unit tests for the SuperCoach settings strict model (D8 drift contract).

Three cases:
  1. The canonical fixture parses cleanly through SuperCoachSettings.
  2. An unknown top-level field raises ValidationError (the envelope guard).
  3. A missing required top-level field raises ValidationError.

The /settings response has ~100 deeply-nested fields; we only model the
four top-level groups (competition, content, game, system) with
`extra="forbid"`. If the upstream adds or renames a top-level section,
the canonical fixture (a real recent response) drives the test to fail.
The agent does not auto-adapt; failure routes to the user per the Miner
charter expansion D8.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from app.miner.supercoach_settings.models import SuperCoachSettings
from pydantic import ValidationError


@pytest.fixture(scope="module")
def fixture_settings(fixtures_dir: Path) -> dict:
    """The canonical SuperCoach /settings response fixture as a raw dict."""
    path = fixtures_dir / "miner" / "supercoach_settings" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_canonical_fixture_parses(fixture_settings):
    """The fixture parses cleanly through SuperCoachSettings.

    Validates the four top-level groups are modeled and that known leaf
    values inside the opaque dicts are present — a smoke check that the
    response is the real settings envelope, not an error stub.
    """
    parsed = SuperCoachSettings.model_validate(fixture_settings)
    assert parsed.system["currency"] == "AUD"
    assert parsed.system["timezone"] == "Australia/Sydney"
    assert "current_round" in parsed.competition
    assert "player_stats" in parsed.game


def test_unknown_top_level_field_raises(fixture_settings):
    """An unknown top-level field trips the envelope guard.

    This is the load-bearing D8 negative test. Without it, we don't know
    that the top-level "extra='forbid'" actually catches a new sibling
    section appearing in the upstream payload.
    """
    bad = copy.deepcopy(fixture_settings)
    bad["loot_boxes"] = {}  # invented top-level section — should not exist
    with pytest.raises(ValidationError) as excinfo:
        SuperCoachSettings.model_validate(bad)
    assert "loot_boxes" in str(excinfo.value)


def test_missing_required_top_level_raises(fixture_settings):
    """Dropping a required top-level group also fails parsing.

    Catches the case where SuperCoach removes or renames a top-level
    section we depend on (e.g. `game` becomes `gameplay`).
    """
    bad = copy.deepcopy(fixture_settings)
    del bad["game"]
    with pytest.raises(ValidationError) as excinfo:
        SuperCoachSettings.model_validate(bad)
    assert "game" in str(excinfo.value)
