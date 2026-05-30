"""Unit tests for the phase_team_lists pure extractor (`_extract_player_list_rows`).

Pure parse/map seam — no S3, no DB. Feeds the real Phase 3 FullTime
match-centre fixture + fake identity maps and asserts the projected
match_team_lists PLAYER rows (coaches are DB-bound and out of unit scope).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.data.populate.phase_team_lists import _extract_player_list_rows


_MATCH_UUID = "33333333-3333-3333-3333-333333333333"
_HOME_UUID = "11111111-1111-1111-1111-111111111111"
_AWAY_UUID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(scope="module")
def payload(fixtures_dir: Path) -> dict:
    path = fixtures_dir / "miner" / "nrlcom_match_centre" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def team_map(payload) -> dict[int, str]:
    return {
        int(payload["homeTeam"]["teamId"]): _HOME_UUID,
        int(payload["awayTeam"]["teamId"]): _AWAY_UUID,
    }


def _full_player_map(payload) -> dict[int, str]:
    return {
        int(p["playerId"]): f"person-{p['playerId']}"
        for side in ("homeTeam", "awayTeam")
        for p in payload[side]["players"]
        if p.get("playerId") is not None
    }


def _resolvable_count(payload) -> int:
    return sum(
        1
        for side in ("homeTeam", "awayTeam")
        for p in payload[side]["players"]
        if p.get("playerId") is not None
    )


def test_extract_player_list_rows(payload, team_map):
    player_map = _full_player_map(payload)
    rows = _extract_player_list_rows(payload, _MATCH_UUID, team_map, player_map)
    assert len(rows) == _resolvable_count(payload)

    # spot-check the first home player
    p0 = payload["homeTeam"]["players"][0]
    r0 = next(r for r in rows if r["player_id"] == f"person-{p0['playerId']}")
    assert r0["match_id"] == _MATCH_UUID
    assert r0["team_id"] == _HOME_UUID
    assert r0["jersey_number"] == p0.get("number")
    assert r0["named_position"] == p0.get("position")

    # is_captain true exactly for the home captain, false for a non-captain
    captain_id = payload["homeTeam"]["captainPlayerId"]
    cap_row = next(r for r in rows if r["player_id"] == f"person-{captain_id}")
    assert cap_row["is_captain"] is True
    non_cap = next(
        r for r in rows
        if r["team_id"] == _HOME_UUID and r["player_id"] != f"person-{captain_id}"
    )
    assert non_cap["is_captain"] is False


def test_skips_unresolved_player(payload, team_map):
    player_map = _full_player_map(payload)
    dropped = payload["homeTeam"]["players"][0]["playerId"]
    player_map.pop(int(dropped))
    rows = _extract_player_list_rows(payload, _MATCH_UUID, team_map, player_map)
    assert len(rows) == _resolvable_count(payload) - 1
    assert all(r["player_id"] != f"person-{dropped}" for r in rows)


def test_skips_unresolved_team(payload):
    # Only the home team is in the map → no away-team rows.
    home_only = {int(payload["homeTeam"]["teamId"]): _HOME_UUID}
    player_map = _full_player_map(payload)
    rows = _extract_player_list_rows(payload, _MATCH_UUID, home_only, player_map)
    home_players = sum(1 for p in payload["homeTeam"]["players"] if p.get("playerId") is not None)
    assert len(rows) == home_players
    assert all(r["team_id"] == _HOME_UUID for r in rows)
