"""Unit tests for the nrl.com casualty-ward strict models (D8 drift contract).

Four cases:
  1. The canonical fixture parses cleanly through NrlcomCasualtyWard.
  2. An unknown top-level field raises ValidationError (envelope guard).
  3. An unknown field on a casualty raises ValidationError (the casualty
     item is modelled strictly because the injuries extractor reads its
     fields by exact key).
  4. A missing required `teamNickname` on a casualty raises ValidationError
     (one of the load-bearing identity fields the extractor resolves on).

If the upstream /casualty-ward/data shape changes — new field, renamed
field, dropped required field — the canonical fixture (a real recent
response) drives the test to fail. The agent does not auto-adapt; failure
routes to the user per the Miner charter expansion D8.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from app.miner.nrlcom_casualty_ward.models import NrlcomCasualtyWard
from pydantic import ValidationError


@pytest.fixture(scope="module")
def fixture_casualty(fixtures_dir: Path) -> dict:
    """The canonical nrl.com /casualty-ward/data response fixture as a raw dict."""
    path = fixtures_dir / "miner" / "nrlcom_casualty_ward" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_canonical_fixture_parses(fixture_casualty):
    """The fixture parses cleanly through NrlcomCasualtyWard.

    Validates the envelope + every casualty, and that the load-bearing
    identity fields are present and non-empty on each.
    """
    parsed = NrlcomCasualtyWard.model_validate(fixture_casualty)
    assert len(parsed.casualties) >= 1
    assert all(c.firstName and c.lastName and c.teamNickname for c in parsed.casualties)


def test_unknown_top_level_field_raises(fixture_casualty):
    """An unknown top-level field trips the envelope guard.

    This is the load-bearing D8 negative test for the envelope.
    """
    bad = copy.deepcopy(fixture_casualty)
    bad["loot_boxes"] = {}  # invented top-level field — should not exist
    with pytest.raises(ValidationError) as excinfo:
        NrlcomCasualtyWard.model_validate(bad)
    assert "loot_boxes" in str(excinfo.value)


def test_unknown_casualty_field_raises(fixture_casualty):
    """Drift on a nested casualty object also trips.

    The casualty item is modelled strictly because the injuries extractor
    reads its fields by exact key — a silent rename would null a column.
    """
    bad = copy.deepcopy(fixture_casualty)
    bad["casualties"][0]["is_retired"] = True  # invented casualty field
    with pytest.raises(ValidationError) as excinfo:
        NrlcomCasualtyWard.model_validate(bad)
    assert "is_retired" in str(excinfo.value)


def test_missing_team_nickname_raises(fixture_casualty):
    """Dropping the load-bearing `teamNickname` fails parsing.

    Catches the case where nrl.com renames or removes one of the identity
    fields the injuries extractor resolves the player/team on.
    """
    bad = copy.deepcopy(fixture_casualty)
    del bad["casualties"][0]["teamNickname"]
    with pytest.raises(ValidationError) as excinfo:
        NrlcomCasualtyWard.model_validate(bad)
    assert "teamNickname" in str(excinfo.value)
