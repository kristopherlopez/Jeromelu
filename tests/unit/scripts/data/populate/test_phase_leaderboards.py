"""Unit tests for the phase_aux stat-leaderboards pure extractor.

`phase_aux.py:populate_stat_leaderboards` projects Scout's nrl.com
/stats/data S3 archives into `stat_leaderboards`. The DB write is a straight
UPSERT; the *mapping* — walk both scope blocks, flatten the four-level
nesting (scope → category → subgroup → leader), float-coerce `value`,
resolve team via nickname lookup, resolve person via `playerId` lookup
(player-scope only) — is pulled into a pure seam (`_extract_leader_rows`)
so it can be tested without S3 or a DB.

Mirrors the TASK-25 treatment of `_extract_standing_rows` / `_casualty_to_row`.

Fixtures reuse the D8 canonical capture committed for TASK-29.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.data.populate.phase_aux import _extract_leader_rows


_STATS_KEY = "scout/nrlcom/stats/111/2026.json"
_ISAAKO_UUID = "11111111-1111-1111-1111-111111111111"
_DOLPHINS_UUID = "22222222-2222-2222-2222-222222222222"
_STORM_UUID = "33333333-3333-3333-3333-333333333333"


# The full column set written into stat_leaderboards. Used to assert
# coverage in the round-trip test.
_EXPECTED_COLUMNS = {
    "competition", "season", "scope", "category", "subgroup", "stat_id",
    "stat_title", "leader_position", "leader_first_name", "leader_last_name",
    "leader_team_nickname", "leader_value", "person_id", "team_id",
    "raw_payload", "s3_archive_key",
}


@pytest.fixture(scope="module")
def stats_payload(fixtures_dir: Path) -> dict:
    """The canonical nrl.com /stats/data response as a raw dict."""
    path = fixtures_dir / "scout" / "nrlcom_stats" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _minimal_player_payload(leader: dict) -> dict:
    """Wrap a single player leader in the four-level nesting `_extract_leader_rows` walks."""
    return {
        "playerStats": [
            {
                "title": "Scoring",
                "groups": [
                    {
                        "title": "Points",
                        "statId": 76,
                        "leaders": [leader],
                    },
                ],
            },
        ],
        "teamStats": [],
    }


def _minimal_team_payload(leader: dict) -> dict:
    """Wrap a single team leader."""
    return {
        "playerStats": [],
        "teamStats": [
            {
                "title": "Scoring",
                "groups": [
                    {
                        "title": "Points",
                        "statId": 76,
                        "leaders": [leader],
                    },
                ],
            },
        ],
    }


def test_one_player_leader_projection():
    """Single player leader → one row, exact field-by-field mapping."""
    payload = _minimal_player_payload({
        "firstName": "Jamayne",
        "lastName": "Isaako",
        "teamNickName": "Dolphins",
        "teamName": "Dolphins",
        "playerId": 502014,
        "value": "134",
        "played": 11,
    })
    rows = _extract_leader_rows(
        payload, key=_STATS_KEY, competition=111, season=2026,
        team_map={"dolphins": _DOLPHINS_UUID},
        player_map={502014: _ISAAKO_UUID},
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["competition"] == 111
    assert row["season"] == 2026
    assert row["scope"] == "player"
    assert row["category"] == "Scoring"
    assert row["subgroup"] == "Points"
    assert row["stat_id"] == 76
    assert row["stat_title"] == "Points"
    assert row["leader_position"] == 1
    assert row["leader_first_name"] == "Jamayne"
    assert row["leader_last_name"] == "Isaako"
    assert row["leader_team_nickname"] == "Dolphins"
    assert row["leader_value"] == 134.0
    assert row["person_id"] == _ISAAKO_UUID
    assert row["team_id"] == _DOLPHINS_UUID
    assert row["s3_archive_key"] == _STATS_KEY
    # raw_payload is the full leader JSON dump.
    assert json.loads(row["raw_payload"])["firstName"] == "Jamayne"


def test_player_scope_resolves_person_id_when_player_id_present():
    """`person_id` resolves via player_map when `playerId` present; None otherwise."""
    # Case 1: playerId present + in map → resolves.
    payload = _minimal_player_payload({
        "firstName": "X", "lastName": "Y", "teamNickName": "Dolphins",
        "teamName": "Dolphins", "playerId": 502014, "value": "10", "played": 1,
    })
    rows = _extract_leader_rows(
        payload, key=_STATS_KEY, competition=111, season=2026,
        team_map={}, player_map={502014: _ISAAKO_UUID},
    )
    assert rows[0]["person_id"] == _ISAAKO_UUID

    # Case 2: playerId present but NOT in map → None.
    rows = _extract_leader_rows(
        payload, key=_STATS_KEY, competition=111, season=2026,
        team_map={}, player_map={},
    )
    assert rows[0]["person_id"] is None

    # Case 3: playerId is None → person_id None (the `if pid:` guard).
    payload_no_pid = _minimal_player_payload({
        "firstName": "X", "lastName": "Y", "teamNickName": "Dolphins",
        "teamName": "Dolphins", "playerId": None, "value": "10", "played": 1,
    })
    rows = _extract_leader_rows(
        payload_no_pid, key=_STATS_KEY, competition=111, season=2026,
        team_map={}, player_map={502014: _ISAAKO_UUID},
    )
    assert rows[0]["person_id"] is None


def test_team_scope_always_emits_person_id_none():
    """Team-scope rows have `person_id is None` regardless of `player_map` contents."""
    payload = _minimal_team_payload({
        "teamNickName": "Storm", "teamName": "Storm", "playerId": 0,
        "value": "350", "played": 11,
    })
    # Stuff player_map with a value that *would* resolve if scope=='player'.
    rows = _extract_leader_rows(
        payload, key=_STATS_KEY, competition=111, season=2026,
        team_map={"storm": _STORM_UUID}, player_map={0: _ISAAKO_UUID},
    )
    assert len(rows) == 1
    assert rows[0]["scope"] == "team"
    assert rows[0]["person_id"] is None
    assert rows[0]["team_id"] == _STORM_UUID


def test_leader_value_float_coercion():
    """`leader_value`: string-int → float; '' → None; None → None; unparseable → None."""
    def value_for(v):
        payload = _minimal_player_payload({
            "firstName": "X", "lastName": "Y", "teamNickName": "X",
            "teamName": "X", "playerId": None, "value": v, "played": 1,
        })
        rows = _extract_leader_rows(
            payload, key=_STATS_KEY, competition=111, season=2026,
            team_map={}, player_map={},
        )
        return rows[0]["leader_value"]

    assert value_for("12.5") == 12.5
    assert value_for("134") == 134.0
    assert value_for("") is None
    assert value_for(None) is None
    assert value_for("abc") is None


def test_team_nickname_lookup():
    """`team_id` resolves via team_map lower-case lookup; falls back to teamName when teamNickName missing; None on unknown."""
    # Case 1: known nickname (lowercased lookup).
    payload = _minimal_player_payload({
        "firstName": "X", "lastName": "Y", "teamNickName": "Storm",
        "teamName": "Storm", "playerId": None, "value": "10", "played": 1,
    })
    rows = _extract_leader_rows(
        payload, key=_STATS_KEY, competition=111, season=2026,
        team_map={"storm": _STORM_UUID}, player_map={},
    )
    assert rows[0]["team_id"] == _STORM_UUID
    assert rows[0]["leader_team_nickname"] == "Storm"

    # Case 2: unknown nickname → None.
    rows = _extract_leader_rows(
        payload, key=_STATS_KEY, competition=111, season=2026,
        team_map={"raiders": "RAIDERS-UUID"}, player_map={},
    )
    assert rows[0]["team_id"] is None

    # Case 3: teamNickName missing → falls back to teamName (per the
    # extractor's `nick = leader.get("teamNickName") or leader.get("teamName") or ""` chain).
    payload_no_nick = _minimal_player_payload({
        "firstName": "X", "lastName": "Y", "teamNickName": None,
        "teamName": "Storm", "playerId": None, "value": "10", "played": 1,
    })
    rows = _extract_leader_rows(
        payload_no_nick, key=_STATS_KEY, competition=111, season=2026,
        team_map={"storm": _STORM_UUID}, player_map={},
    )
    assert rows[0]["team_id"] == _STORM_UUID
    assert rows[0]["leader_team_nickname"] == "Storm"


def test_canonical_fixture_round_trip(stats_payload):
    """Loading the real fixture should produce rows covering every subgroup,
    each row carrying the full column set + the correct s3_archive_key.
    """
    rows = _extract_leader_rows(
        stats_payload, key=_STATS_KEY, competition=111, season=2026,
        team_map={}, player_map={},
    )
    # Lower bound: at least one row per subgroup (the fixture has 37 player
    # + 33 team subgroups = 70 total). Per-subgroup row count varies (≤5
    # leaders observed), so this is a coarse lower bound.
    n_subgroups = (
        sum(len(c["groups"]) for c in stats_payload.get("playerStats", []))
        + sum(len(c["groups"]) for c in stats_payload.get("teamStats", []))
    )
    assert len(rows) >= n_subgroups, (
        f"expected ≥{n_subgroups} rows (one per subgroup), got {len(rows)}"
    )
    # Every row has the full column set.
    for row in rows:
        assert set(row.keys()) == _EXPECTED_COLUMNS, (
            f"row keys diverge: missing={_EXPECTED_COLUMNS - set(row.keys())}, "
            f"extra={set(row.keys()) - _EXPECTED_COLUMNS}"
        )
        assert row["s3_archive_key"] == _STATS_KEY
        assert row["leader_position"] >= 1
        assert row["scope"] in ("player", "team")
    # Both scopes represented.
    scopes = {row["scope"] for row in rows}
    assert scopes == {"player", "team"}
