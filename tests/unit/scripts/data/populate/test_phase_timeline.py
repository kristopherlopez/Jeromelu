"""Unit tests for the phase_timeline pure extractors.

`_extract_timeline_rows` and `_extract_official_rows` are pure parse/map
seams — no S3, no DB. Fed the real Phase 3 FullTime match-centre fixture +
fake identity maps.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.data.populate.phase_timeline import (
    _extract_official_rows,
    _extract_timeline_rows,
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


def test_extract_timeline_rows(payload, team_map):
    rows = _extract_timeline_rows(payload, _KEY, _MATCH_UUID, team_map, player_map={})
    timeline = payload["timeline"]
    # one row per event, sequence 0..N-1 in order
    assert len(rows) == len(timeline)
    assert [r["sequence"] for r in rows] == list(range(len(timeline)))
    assert all(r["match_id"] == _MATCH_UUID and r["s3_archive_key"] == _KEY for r in rows)
    assert all(r["nrlcom_match_id"] == str(payload["matchId"]) for r in rows)

    # running scores map from homeScore/awayScore
    idx, ev = next(
        (i, e) for i, e in enumerate(timeline) if e.get("homeScore") is not None
    )
    assert rows[idx]["running_home_score"] == ev["homeScore"]
    assert rows[idx]["running_away_score"] == ev.get("awayScore")

    # team resolution via the map (an event with a teamId in the map)
    tidx, tev = next(
        (i, e) for i, e in enumerate(timeline)
        if e.get("teamId") and int(e["teamId"]) in team_map
    )
    assert rows[tidx]["team_id"] == team_map[int(tev["teamId"])]
    assert rows[tidx]["nrlcom_team_id"] == int(tev["teamId"])


def test_event_type_defaults_to_unknown(payload, team_map):
    bad = copy.deepcopy(payload)
    bad["timeline"][0]["type"] = None
    rows = _extract_timeline_rows(bad, _KEY, _MATCH_UUID, team_map, player_map={})
    assert rows[0]["event_type"] == "Unknown"


def test_extract_official_rows(payload):
    rows = _extract_official_rows(payload, _KEY, _MATCH_UUID)
    named = [
        o for o in payload["officials"]
        if (o.get("firstName") or "").strip() or (o.get("lastName") or "").strip()
    ]
    assert len(rows) == len(named)
    # role from position; person_id always None; ids carried through
    for r in rows:
        assert r["person_id"] is None
        assert r["match_id"] == _MATCH_UUID
        assert r["nrlcom_match_id"] == str(payload["matchId"])


def test_official_without_name_is_skipped(payload):
    bad = copy.deepcopy(payload)
    bad["officials"] = list(bad["officials"]) + [{"firstName": "", "lastName": "", "position": "Ghost"}]
    rows = _extract_official_rows(bad, _KEY, _MATCH_UUID)
    named = [
        o for o in payload["officials"]
        if (o.get("firstName") or "").strip() or (o.get("lastName") or "").strip()
    ]
    assert len(rows) == len(named)  # the empty-name official added no row
