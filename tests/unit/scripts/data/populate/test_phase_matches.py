"""Unit tests for the phase_matches pure extractor (`_extract_one`).

`_extract_one(payload, key, team_map, venue_map)` is the pure parse/map
seam — no S3, no DB. We feed the real Phase 3 match-centre fixture (a
FullTime raiders-v-dolphins R12 payload) plus fake identity maps and
assert the projected `matches` row.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.data.populate.phase_matches import (
    _GRADE_MAP,
    _KEY_RE,
    _extract_one,
    _normalize_status,
)


_KEY = "scout/nrlcom/match-centre/111/2026/round-12/raiders-v-dolphins.json"
_HOME_UUID = "11111111-1111-1111-1111-111111111111"
_AWAY_UUID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(scope="module")
def payload(fixtures_dir: Path) -> dict:
    """The real FullTime match-centre fixture (reused from Phase 3)."""
    path = fixtures_dir / "scout" / "nrlcom_match_centre" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def team_map(payload) -> dict[int, str]:
    """nrlcom_team_id → team_id (str), built from the fixture's two teams."""
    return {
        int(payload["homeTeam"]["teamId"]): _HOME_UUID,
        int(payload["awayTeam"]["teamId"]): _AWAY_UUID,
    }


def test_extract_one_maps_core_fields(payload, team_map):
    row = _extract_one(payload, _KEY, team_map, venue_map={})
    assert row is not None
    assert row["source"] == "nrl_com"
    assert row["external_match_id"] == str(payload["matchId"])
    assert row["season"] == 2026
    assert row["round"] == 12
    assert row["grade"] == "nrl"
    assert row["status"] == "final"  # FullTime → final
    assert row["home_team_id"] == _HOME_UUID
    assert row["away_team_id"] == _AWAY_UUID
    # Referee pulled from officials[] (a played match has one)
    assert isinstance(row["referee_name"], str) and row["referee_name"].strip()


def test_attendance_zero_becomes_null(payload, team_map):
    bad = copy.deepcopy(payload)
    bad["attendance"] = 0
    row = _extract_one(bad, _KEY, team_map, venue_map={})
    assert row["attendance"] is None


def test_unresolved_team_returns_none(payload):
    # Empty team_map → home/away can't resolve → skip-no-team
    assert _extract_one(payload, _KEY, team_map={}, venue_map={}) is None


def test_same_team_returns_none(payload):
    # Both teamIds mapped to the same team_id → distinct-teams guard
    same = {
        int(payload["homeTeam"]["teamId"]): _HOME_UUID,
        int(payload["awayTeam"]["teamId"]): _HOME_UUID,
    }
    assert _extract_one(payload, _KEY, same, venue_map={}) is None


def test_key_regex_and_status_map():
    m = _KEY_RE.search(_KEY)
    assert m is not None
    assert m.group("comp") == "111"
    assert m.group("season") == "2026"
    assert m.group("round") == "12"
    assert m.group("slug") == "raiders-v-dolphins"
    assert _normalize_status("FullTime") == "final"
    assert _normalize_status("Upcoming") == "scheduled"
    assert _normalize_status(None) == "scheduled"
    assert _GRADE_MAP[111] == "nrl"
