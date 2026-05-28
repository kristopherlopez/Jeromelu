"""Unit tests for the nrl.com /players/data strict models (D8 drift contract).

Four cases:
  1. The canonical fixture parses cleanly through NrlcomPlayersRoster.
  2. An unknown top-level field raises ValidationError (envelope guard).
  3. An unknown field on a `profiles[]` item raises ValidationError —
     proves a newly-added profile-level key from upstream surfaces as
     drift, not silently dropped (the profile is modelled strictly so
     any future extractor reading by exact key gets the drift signal).
  4. A missing required `teamNickName` on a profile raises ValidationError
     — one of the load-bearing identity fields any future extractor will
     resolve the team on (same precedent as the casualty/ladder tests).

If the upstream /players/data shape changes — new field, renamed field,
dropped required field — the canonical fixture (a real recent response)
drives the test to fail. The agent does not auto-adapt; failure routes to
the user per the Scout charter expansion D8.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from app.scout.nrlcom_players_roster.models import NrlcomPlayersRoster
from pydantic import ValidationError


@pytest.fixture(scope="module")
def fixture_players_roster(fixtures_dir: Path) -> dict:
    """The canonical nrl.com /players/data response fixture as a raw dict."""
    path = fixtures_dir / "scout" / "nrlcom_players_roster" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_canonical_fixture_parses(fixture_players_roster):
    """The fixture parses cleanly through NrlcomPlayersRoster.

    Validates the envelope + at least one populated profileGroup and
    profile end-to-end, and that the load-bearing identity fields are
    present on each profile.
    """
    parsed = NrlcomPlayersRoster.model_validate(fixture_players_roster)
    assert len(parsed.profileGroups) >= 1
    assert len(parsed.profileGroups[0].profiles) >= 1
    # Identity fields populated on at least the first profile.
    p0 = parsed.profileGroups[0].profiles[0]
    assert p0.firstName is not None
    assert p0.lastName is not None
    assert p0.teamNickName is not None


def test_unknown_top_level_field_raises(fixture_players_roster):
    """An unknown top-level field trips the envelope guard.

    Load-bearing D8 negative test for the envelope.
    """
    bad = copy.deepcopy(fixture_players_roster)
    bad["loot_boxes"] = {}  # invented top-level field — should not exist
    with pytest.raises(ValidationError) as excinfo:
        NrlcomPlayersRoster.model_validate(bad)
    assert "loot_boxes" in str(excinfo.value)


def test_unknown_profile_field_raises(fixture_players_roster):
    """Drift on a nested profile object also trips.

    The profile is modelled strictly so any future extractor reading by
    exact key gets the drift signal — a new profile-level key (e.g.
    upstream adds `jerseyNumber`) must surface as drift, not be silently
    dropped.
    """
    bad = copy.deepcopy(fixture_players_roster)
    bad["profileGroups"][0]["profiles"][0]["is_retired"] = True
    with pytest.raises(ValidationError) as excinfo:
        NrlcomPlayersRoster.model_validate(bad)
    assert "is_retired" in str(excinfo.value)


def test_missing_team_nickname_raises(fixture_players_roster):
    """Dropping the load-bearing `teamNickName` on a profile fails parsing.

    `teamNickName` is the identity field any future extractor will resolve
    the team on — same load-bearing role as on casualty / ladder.
    """
    bad = copy.deepcopy(fixture_players_roster)
    del bad["profileGroups"][0]["profiles"][0]["teamNickName"]
    with pytest.raises(ValidationError) as excinfo:
        NrlcomPlayersRoster.model_validate(bad)
    assert "teamNickName" in str(excinfo.value)
