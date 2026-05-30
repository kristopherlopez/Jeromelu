"""Unit tests for the SuperCoach roster strict Pydantic models (D8 drift contract).

Three cases:
  1. The canonical fixture parses cleanly through every model.
  2. An unknown field on the player envelope raises ValidationError.
  3. A missing required field on the player envelope raises ValidationError.

If the upstream SuperCoach response shape changes — new field, renamed
field, dropped required field — the canonical fixture (a real recent
response, trimmed to ~34 players across 17 teams) drives the test to
fail. The agent does not auto-adapt; failure routes to the user per
the Miner charter expansion D8.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from app.miner.supercoach_roster.models import SuperCoachPlayer
from pydantic import ValidationError


@pytest.fixture(scope="module")
def fixture_players(fixtures_dir: Path) -> list[dict]:
    """The canonical SuperCoach response fixture as raw dicts."""
    path = fixtures_dir / "miner" / "supercoach_roster" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_canonical_fixture_parses(fixture_players):
    """Every player in the fixture parses cleanly through SuperCoachPlayer.

    Validates the structural envelope (player, team, played_status,
    positions) is fully modeled. The opaque lists (player_stats, odds,
    notes) pass through as dicts without strict validation per design.
    """
    parsed = [SuperCoachPlayer.model_validate(p) for p in fixture_players]
    assert len(parsed) == len(fixture_players)
    # Sanity check on a known structural field
    assert all(p.team.abbrev for p in parsed)
    # All 17 NRL teams represented
    teams = {p.team.abbrev for p in parsed}
    assert len(teams) == 17, f"Expected 17 teams in fixture, got {sorted(teams)}"


def test_unknown_field_on_player_raises(fixture_players):
    """An unknown top-level player field trips the drift detection.

    This is the load-bearing negative test. Without it, we don't know
    that D8's "extra='forbid'" actually catches drift.
    """
    bad = copy.deepcopy(fixture_players[0])
    bad["is_byzantine_rookie"] = True  # invented field — should not exist
    with pytest.raises(ValidationError) as excinfo:
        SuperCoachPlayer.model_validate(bad)
    # The error message should name the unknown field for actionable diagnosis
    assert "is_byzantine_rookie" in str(excinfo.value)


def test_unknown_field_on_nested_team_raises(fixture_players):
    """Drift on the nested Team object also trips."""
    bad = copy.deepcopy(fixture_players[0])
    bad["team"]["is_relegated"] = False  # invented field
    with pytest.raises(ValidationError) as excinfo:
        SuperCoachPlayer.model_validate(bad)
    assert "is_relegated" in str(excinfo.value)


def test_missing_required_field_raises(fixture_players):
    """Dropping a required envelope field also fails parsing.

    Catches the case where SuperCoach removes or renames a field we
    depend on (e.g. `team_id` becomes `tid`).
    """
    bad = copy.deepcopy(fixture_players[0])
    del bad["team_id"]
    with pytest.raises(ValidationError) as excinfo:
        SuperCoachPlayer.model_validate(bad)
    assert "team_id" in str(excinfo.value)
