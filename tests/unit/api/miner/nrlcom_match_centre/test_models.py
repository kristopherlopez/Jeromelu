"""Unit tests for the nrl.com match-centre strict envelope model (D8 contract).

Four cases:
  1. The canonical (FullTime) fixture parses cleanly through NrlcomMatchCentre.
  2. The Upcoming fixture parses too — the envelope is match-state-dependent
     (FullTime and Upcoming carry different top-level sections), so the model's
     optional/required split must accept both.
  3. An unknown top-level field raises ValidationError (envelope guard).
  4. A missing `matchId` raises ValidationError (the load-bearing field).

If the upstream match-centre shape changes — a new top-level section, a
renamed/removed shared field — the canonical fixtures (real recent responses)
drive the test to fail. The agent does not auto-adapt; failure routes to the
user per the Miner charter expansion D8.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from app.miner.nrlcom_match_centre.models import NrlcomMatchCentre
from pydantic import ValidationError


@pytest.fixture(scope="module")
def fixture_match_centre(fixtures_dir: Path) -> dict:
    """The canonical (FullTime) match-centre response fixture as a raw dict."""
    path = fixtures_dir / "miner" / "nrlcom_match_centre" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fixture_match_centre_upcoming(fixtures_dir: Path) -> dict:
    """An Upcoming match-centre response — the alternate envelope shape."""
    path = fixtures_dir / "miner" / "nrlcom_match_centre" / "canonical_response_upcoming.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_canonical_fixture_parses(fixture_match_centre):
    """The FullTime fixture parses cleanly through NrlcomMatchCentre.

    Validates the result-only sections (timeline, stats) are present on a
    played match.
    """
    parsed = NrlcomMatchCentre.model_validate(fixture_match_centre)
    assert parsed.matchId
    assert isinstance(parsed.timeline, list)
    assert isinstance(parsed.stats, dict)


def test_upcoming_fixture_parses(fixture_match_centre_upcoming):
    """The Upcoming fixture parses too — result-only sections are absent and
    broadcast sections are present, but the envelope still validates."""
    parsed = NrlcomMatchCentre.model_validate(fixture_match_centre_upcoming)
    assert parsed.matchId
    assert parsed.matchState == "Upcoming"
    assert parsed.timeline is None  # absent before the match is played
    assert isinstance(parsed.broadcastChannels, list)


def test_unknown_top_level_field_raises(fixture_match_centre):
    """An unknown top-level field trips the envelope guard.

    This is the load-bearing D8 negative test — a new top-level section
    (outside the FullTime ∪ Upcoming union) must fail.
    """
    bad = copy.deepcopy(fixture_match_centre)
    bad["is_replay"] = True  # invented top-level field — should not exist
    with pytest.raises(ValidationError) as excinfo:
        NrlcomMatchCentre.model_validate(bad)
    assert "is_replay" in str(excinfo.value)


def test_missing_matchid_raises(fixture_match_centre):
    """Dropping the load-bearing `matchId` fails parsing."""
    bad = copy.deepcopy(fixture_match_centre)
    del bad["matchId"]
    with pytest.raises(ValidationError) as excinfo:
        NrlcomMatchCentre.model_validate(bad)
    assert "matchId" in str(excinfo.value)
