"""Unit tests for the phase_stats pure extractor (`_extract_stat_rows`).

`_extract_stat_rows(payload, key, match_id, team_map, player_map)` is the
pure parse/map seam — no S3, no DB. We feed the real Phase 3 FullTime
match-centre fixture plus fake identity maps and assert the projected
`player_match_stats` rows (camelCase→snake_case field mapping, roster meta,
identity resolution).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.data.populate.phase_stats import (
    _FIELD_MAP,
    _build_player_meta_map,
    _extract_stat_rows,
)


_KEY = "miner/nrlcom/match-centre/111/2026/round-12/raiders-v-dolphins.json"
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


def _first_home_stat_player(payload) -> dict:
    return payload["stats"]["players"]["homeTeam"][0]


def test_build_player_meta_map(payload):
    meta = _build_player_meta_map(payload)
    # Every rostered player across both squads is present
    rostered = [
        p["playerId"]
        for side in ("homeTeam", "awayTeam")
        for p in payload[side]["players"]
        if p.get("playerId") is not None
    ]
    assert len(meta) == len(rostered)
    # Spot-check the first home player's meta
    p0 = payload["homeTeam"]["players"][0]
    m0 = meta[int(p0["playerId"])]
    assert m0["jersey_number"] == p0.get("number")
    assert m0["position"] == p0.get("position")
    assert m0["is_home"] is True
    assert m0["nrlcom_team_id"] == int(payload["homeTeam"]["teamId"])


def test_extract_stat_rows_field_mapping(payload, team_map):
    sp = _first_home_stat_player(payload)
    pid = int(sp["playerId"])
    player_map = {pid: "person-uuid-aaaa"}

    rows = _extract_stat_rows(payload, _KEY, _MATCH_UUID, team_map, player_map)
    row = next(r for r in rows if r["nrlcom_player_id"] == pid)

    # camelCase upstream → snake_case column, per _FIELD_MAP
    assert row["tackles_made"] == sp.get("tacklesMade")
    assert row["all_run_metres"] == sp.get("allRunMetres")
    assert row["tries"] == sp.get("tries")
    # roster meta
    meta = _build_player_meta_map(payload)[pid]
    assert row["jersey_number"] == meta["jersey_number"]
    assert row["position"] == meta["position"]
    assert row["is_on_field"] == meta["is_on_field"]
    assert row["is_home"] is True
    # passed-in match_id + key + resolved identity
    assert row["match_id"] == _MATCH_UUID
    assert row["s3_archive_key"] == _KEY
    assert row["nrlcom_match_id"] == str(payload["matchId"])
    assert row["person_id"] == "person-uuid-aaaa"
    assert row["team_id"] == _HOME_UUID
    # every _FIELD_MAP destination column is present on the row
    assert all(dst in row for dst in _FIELD_MAP.values())


def test_person_and_team_resolution_nullable(payload, team_map):
    sp = _first_home_stat_player(payload)
    pid = int(sp["playerId"])
    # Empty maps → person_id / team_id None, but the row is still emitted
    rows = _extract_stat_rows(payload, _KEY, _MATCH_UUID, team_map={}, player_map={})
    row = next(r for r in rows if r["nrlcom_player_id"] == pid)
    assert row["person_id"] is None
    assert row["team_id"] is None


def test_row_count_equals_stat_players(payload, team_map):
    rows = _extract_stat_rows(payload, _KEY, _MATCH_UUID, team_map, player_map={})
    expected = sum(
        1
        for side in ("homeTeam", "awayTeam")
        for s in payload["stats"]["players"].get(side) or []
        if s.get("playerId") is not None
    )
    assert len(rows) == expected
