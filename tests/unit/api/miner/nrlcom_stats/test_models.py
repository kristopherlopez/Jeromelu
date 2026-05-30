"""Unit tests for the nrl.com /stats/data strict models (D8 drift contract).

Four cases:
  1. The canonical fixture parses cleanly through NrlcomStats — including
     both player-scope and team-scope leader shapes (the player-only
     identity fields are absent on team leaders by design).
  2. An unknown top-level field raises ValidationError (envelope guard).
  3. An unknown field on a `leaders[]` item raises ValidationError — proves
     a newly-added leader-level key from upstream surfaces as drift, not
     silently dropped (the leader is modelled strictly because the
     leaderboards extractor reads its fields by exact key).
  4. A missing required `title` on a category raises ValidationError —
     `title` is load-bearing (the extractor reads it for the `category` DB
     column).

If the upstream /stats/data shape changes — new field, renamed field,
dropped required field — the canonical fixture (a real recent response)
drives the test to fail. The agent does not auto-adapt; failure routes to
the user per the Miner charter expansion D8.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from app.miner.nrlcom_stats.models import NrlcomStats
from pydantic import ValidationError


@pytest.fixture(scope="module")
def fixture_stats(fixtures_dir: Path) -> dict:
    """The canonical nrl.com /stats/data response fixture as a raw dict."""
    path = fixtures_dir / "miner" / "nrlcom_stats" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_canonical_fixture_parses(fixture_stats):
    """The fixture parses cleanly through NrlcomStats.

    Validates the four-level envelope + at least one populated leader in
    each scope. Also proves the player-vs-team leader bifurcation handles
    cleanly under one model — team leaders parse without the player-only
    `firstName`/`lastName`/`headImage`/`bodyImage` keys.
    """
    parsed = NrlcomStats.model_validate(fixture_stats)
    assert len(parsed.playerStats) >= 1
    assert len(parsed.teamStats) >= 1
    # End-to-end nested population: at least one populated leader on each scope.
    first_player_leader = parsed.playerStats[0].groups[0].leaders[0]
    first_team_leader = parsed.teamStats[0].groups[0].leaders[0]
    # Player leader has the player-only identity fields.
    assert first_player_leader.firstName is not None
    assert first_player_leader.lastName is not None
    # Team leader correctly has them defaulted to None (the key wasn't in the
    # upstream payload at all — this is the player-vs-team bifurcation).
    assert first_team_leader.firstName is None
    assert first_team_leader.lastName is None
    # Universal identity field present on both.
    assert first_player_leader.teamNickName is not None
    assert first_team_leader.teamNickName is not None


def test_unknown_top_level_field_raises(fixture_stats):
    """An unknown top-level field trips the envelope guard.

    Load-bearing D8 negative test for the envelope.
    """
    bad = copy.deepcopy(fixture_stats)
    bad["loot_boxes"] = {}  # invented top-level field — should not exist
    with pytest.raises(ValidationError) as excinfo:
        NrlcomStats.model_validate(bad)
    assert "loot_boxes" in str(excinfo.value)


def test_unknown_leader_field_raises(fixture_stats):
    """Drift on a nested leader object also trips.

    The leader is modelled strictly because the leaderboards extractor reads
    its fields by exact key — a silent rename or addition would null/skip a
    column. A new leader-level key (e.g. upstream adds a `tries_per_game`)
    must surface as drift, not be silently dropped.
    """
    bad = copy.deepcopy(fixture_stats)
    bad["playerStats"][0]["groups"][0]["leaders"][0]["is_retired"] = True
    with pytest.raises(ValidationError) as excinfo:
        NrlcomStats.model_validate(bad)
    assert "is_retired" in str(excinfo.value)


def test_missing_required_category_title_raises(fixture_stats):
    """Dropping the load-bearing `title` on a category fails parsing.

    Catches the case where nrl.com renames or removes the field the
    leaderboards extractor reads for the `category` DB column.
    """
    bad = copy.deepcopy(fixture_stats)
    del bad["playerStats"][0]["title"]
    with pytest.raises(ValidationError) as excinfo:
        NrlcomStats.model_validate(bad)
    assert "title" in str(excinfo.value)
