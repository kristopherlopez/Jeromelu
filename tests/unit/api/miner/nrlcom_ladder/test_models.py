"""Unit tests for the nrl.com ladder strict models (D8 drift contract).

Four cases:
  1. The canonical fixture parses cleanly through NrlcomLadder, and the
     space-aliased stats (e.g. `points for` → `points_for`) populate.
  2. An unknown top-level field raises ValidationError (envelope guard).
  3. An unknown `stats` key raises ValidationError — proves a newly-added
     metric trips drift (the stats object is modelled strictly because the
     standings extractor reads every metric by exact key).
  4. A missing required `teamNickname` on a position raises ValidationError
     (the load-bearing field the extractor resolves the team on).

If the upstream /ladder/data shape changes — new field, renamed field,
dropped required field — the canonical fixture (a real recent response)
drives the test to fail. The agent does not auto-adapt; failure routes to
the user per the Miner charter expansion D8.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from app.miner.nrlcom_ladder.models import NrlcomLadder
from pydantic import ValidationError


@pytest.fixture(scope="module")
def fixture_ladder(fixtures_dir: Path) -> dict:
    """The canonical nrl.com /ladder/data response fixture as a raw dict."""
    path = fixtures_dir / "miner" / "nrlcom_ladder" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_canonical_fixture_parses(fixture_ladder):
    """The fixture parses cleanly through NrlcomLadder.

    Validates the envelope + every position, that the load-bearing
    `teamNickname` is present, and that the space-aliased stats map onto
    their Python field names (so a `points for` key reaches `points_for`).
    """
    parsed = NrlcomLadder.model_validate(fixture_ladder)
    assert len(parsed.positions) >= 1
    assert all(p.teamNickname for p in parsed.positions)
    # Alias mapping proof: the space-keyed upstream metrics reach their fields.
    first = parsed.positions[0].stats
    assert first.points_for is not None
    assert first.points_against is not None
    assert first.average_winning_margin is not None


def test_unknown_top_level_field_raises(fixture_ladder):
    """An unknown top-level field trips the envelope guard."""
    bad = copy.deepcopy(fixture_ladder)
    bad["loot_boxes"] = {}  # invented top-level field — should not exist
    with pytest.raises(ValidationError) as excinfo:
        NrlcomLadder.model_validate(bad)
    assert "loot_boxes" in str(excinfo.value)


def test_unknown_stats_key_raises(fixture_ladder):
    """Drift on the nested `stats` object also trips.

    The stats object is modelled strictly because the standings extractor
    reads every metric by exact key — a new metric must surface, not be
    silently dropped.
    """
    bad = copy.deepcopy(fixture_ladder)
    bad["positions"][0]["stats"]["tries scored"] = 99  # invented metric
    with pytest.raises(ValidationError) as excinfo:
        NrlcomLadder.model_validate(bad)
    assert "tries scored" in str(excinfo.value)


def test_missing_team_nickname_raises(fixture_ladder):
    """Dropping the load-bearing `teamNickname` fails parsing.

    Catches the case where nrl.com renames or removes the field the
    standings extractor resolves the team on.
    """
    bad = copy.deepcopy(fixture_ladder)
    del bad["positions"][0]["teamNickname"]
    with pytest.raises(ValidationError) as excinfo:
        NrlcomLadder.model_validate(bad)
    assert "teamNickname" in str(excinfo.value)
