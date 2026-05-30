"""Unit tests for the SuperCoach teams strict Pydantic models (D8 drift contract).

Four cases:
  1. The canonical fixture parses cleanly through every model.
  2. An unknown field on the team envelope raises ValidationError.
  3. An unknown field on the nested competition object raises ValidationError.
  4. A missing required field on the team envelope raises ValidationError.

If the upstream SuperCoach response shape changes — new field, renamed
field, dropped required field — the canonical fixture (a real recent
response of all 17 NRL teams) drives the test to fail. The agent does
not auto-adapt; failure routes to the user per the Miner charter
expansion D8.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from app.miner.supercoach_teams.models import SuperCoachTeam
from pydantic import ValidationError


@pytest.fixture(scope="module")
def fixture_teams(fixtures_dir: Path) -> list[dict]:
    """The canonical SuperCoach /teams response fixture as raw dicts."""
    path = fixtures_dir / "miner" / "supercoach_teams" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_canonical_fixture_parses(fixture_teams):
    """Every team in the fixture parses cleanly through SuperCoachTeam.

    Validates the structural envelope (id, abbrev, feed_name, name, and
    the nested competition object) is fully modeled, that all 17 NRL
    teams are present with distinct abbrevs, and that the competition is
    the NRL competition (id 2) for every row.
    """
    parsed = [SuperCoachTeam.model_validate(t) for t in fixture_teams]
    assert len(parsed) == 17
    # No duplicate abbrevs — one row per club
    assert len({t.abbrev for t in parsed}) == 17
    # Every team belongs to the NRL competition
    assert all(t.competition.id == 2 for t in parsed)
    assert all(t.competition.name == "NRL" for t in parsed)


def test_unknown_field_on_team_raises(fixture_teams):
    """An unknown top-level team field trips the drift detection.

    This is the load-bearing negative test. Without it, we don't know
    that D8's "extra='forbid'" actually catches drift.
    """
    bad = copy.deepcopy(fixture_teams[0])
    bad["is_new_franchise"] = True  # invented field — should not exist
    with pytest.raises(ValidationError) as excinfo:
        SuperCoachTeam.model_validate(bad)
    # The error message should name the unknown field for actionable diagnosis
    assert "is_new_franchise" in str(excinfo.value)


def test_unknown_field_on_nested_competition_raises(fixture_teams):
    """Drift on the nested competition object also trips."""
    bad = copy.deepcopy(fixture_teams[0])
    bad["competition"]["is_super_league"] = False  # invented field
    with pytest.raises(ValidationError) as excinfo:
        SuperCoachTeam.model_validate(bad)
    assert "is_super_league" in str(excinfo.value)


def test_missing_required_field_raises(fixture_teams):
    """Dropping a required envelope field also fails parsing.

    Catches the case where SuperCoach removes or renames a field we
    depend on (e.g. `abbrev` becomes `code`).
    """
    bad = copy.deepcopy(fixture_teams[0])
    del bad["abbrev"]
    with pytest.raises(ValidationError) as excinfo:
        SuperCoachTeam.model_validate(bad)
    assert "abbrev" in str(excinfo.value)
