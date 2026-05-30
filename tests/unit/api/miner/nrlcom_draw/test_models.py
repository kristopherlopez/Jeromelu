"""Unit tests for the nrl.com draw strict models (D8 drift contract).

Four cases:
  1. The canonical fixture parses cleanly through NrlcomDraw.
  2. An unknown top-level field raises ValidationError (envelope guard).
  3. An unknown field on a fixture raises ValidationError.
  4. A missing `matchCentreUrl` on a fixture raises ValidationError (the
     load-bearing field the match-centre pipeline walks).

If the upstream /draw/data shape changes — new field, renamed field,
dropped required field — the canonical fixture (a real recent response)
drives the test to fail. The agent does not auto-adapt; failure routes to
the user per the Miner charter expansion D8.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from app.miner.nrlcom_draw.models import NrlcomDraw
from pydantic import ValidationError


@pytest.fixture(scope="module")
def fixture_draw(fixtures_dir: Path) -> dict:
    """The canonical nrl.com /draw/data response fixture as a raw dict."""
    path = fixtures_dir / "miner" / "nrlcom_draw" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_canonical_fixture_parses(fixture_draw):
    """The fixture parses cleanly through NrlcomDraw.

    Validates the envelope + every fixture, and that the load-bearing
    `matchCentreUrl` is present and non-empty on each.
    """
    parsed = NrlcomDraw.model_validate(fixture_draw)
    assert len(parsed.fixtures) >= 1
    assert all(isinstance(f.matchCentreUrl, str) and f.matchCentreUrl for f in parsed.fixtures)


def test_unknown_top_level_field_raises(fixture_draw):
    """An unknown top-level field trips the envelope guard.

    This is the load-bearing D8 negative test for the envelope.
    """
    bad = copy.deepcopy(fixture_draw)
    bad["loot_boxes"] = {}  # invented top-level field — should not exist
    with pytest.raises(ValidationError) as excinfo:
        NrlcomDraw.model_validate(bad)
    assert "loot_boxes" in str(excinfo.value)


def test_unknown_fixture_field_raises(fixture_draw):
    """Drift on a nested fixture object also trips."""
    bad = copy.deepcopy(fixture_draw)
    bad["fixtures"][0]["is_grand_final"] = True  # invented fixture field
    with pytest.raises(ValidationError) as excinfo:
        NrlcomDraw.model_validate(bad)
    assert "is_grand_final" in str(excinfo.value)


def test_missing_matchcentreurl_raises(fixture_draw):
    """Dropping the load-bearing `matchCentreUrl` fails parsing.

    Catches the case where nrl.com renames or removes the field the
    match-centre pipeline depends on to discover each match.
    """
    bad = copy.deepcopy(fixture_draw)
    del bad["fixtures"][0]["matchCentreUrl"]
    with pytest.raises(ValidationError) as excinfo:
        NrlcomDraw.model_validate(bad)
    assert "matchCentreUrl" in str(excinfo.value)
