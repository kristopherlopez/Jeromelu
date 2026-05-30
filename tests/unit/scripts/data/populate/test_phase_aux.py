"""Unit tests for the phase_aux pure extractors.

`phase_aux.py` projects Miner's nrl.com ladder + casualty-ward S3 archives
into `team_standings` / `injuries`. The DB writes are a state machine (and a
straight UPSERT); the *mapping* is pulled into pure seams so it can be tested
without S3 or a DB:

  - `_extract_standing_rows(payload, ...)` — one team_standings row per
    ladder position (incl. the 22 space-keyed metrics + the enumerate-index
    fallback for `ladder_position`).
  - `_casualty_to_row(c, ...)` — derived fields for one casualty (or None on
    skip), which the injuries state machine then opens/closes rows from.
  - `_bucket_status(text, current_round)` — maps an `expectedReturn` string to
    the `injuries.status` enum.

Fixtures reuse the D8 canonical captures committed for TASK-21 / TASK-23.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.data.populate.phase_aux import (
    _bucket_status,
    _casualty_to_row,
    _extract_standing_rows,
)


_PANTHERS = "11111111-1111-1111-1111-111111111111"
_LADDER_KEY = "miner/nrlcom/ladder/111/2026/round-12.json"


@pytest.fixture(scope="module")
def ladder_payload(fixtures_dir: Path) -> dict:
    path = fixtures_dir / "miner" / "nrlcom_ladder" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def casualty_payload(fixtures_dir: Path) -> dict:
    path = fixtures_dir / "miner" / "nrlcom_casualty_ward" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ── _extract_standing_rows ────────────────────────────────────────────────

def test_standing_rows_map_all_22_metrics(ladder_payload):
    """Every space-keyed stat lands in its snake_case column, with the
    envelope coordinates (competition/season/round) bound from the caller."""
    positions = ladder_payload["positions"]
    nick0 = positions[0]["teamNickname"]
    team_map = {nick0.lower(): _PANTHERS}  # resolve only the leader

    rows = _extract_standing_rows(
        ladder_payload,
        key=_LADDER_KEY,
        competition=111,
        season=2026,
        round_no=12,
        team_map=team_map,
    )

    assert len(rows) == len(positions)
    r0 = rows[0]
    s0 = positions[0]["stats"]
    assert r0["competition"] == 111
    assert r0["season"] == 2026
    assert r0["round"] == 12
    assert r0["nrlcom_team_nickname"] == nick0
    assert r0["team_id"] == _PANTHERS  # resolved by nickname
    assert r0["s3_archive_key"] == _LADDER_KEY
    # Space-key → snake_case column mapping (the load-bearing aliasing)
    assert r0["points_for"] == s0["points for"]
    assert r0["points_against"] == s0["points against"]
    assert r0["points_difference"] == s0["points difference"]
    assert r0["bonus_points"] == s0["bonus points"]
    assert r0["home_record"] == s0["home record"]
    assert r0["away_record"] == s0["away record"]
    assert r0["day_record"] == s0["day record"]
    assert r0["night_record"] == s0["night record"]
    assert r0["average_winning_margin"] == s0["average winning margin"]
    assert r0["average_losing_margin"] == s0["average losing margin"]
    assert r0["close_games"] == s0["close games"]
    assert r0["golden_point"] == s0["golden point"]
    assert r0["players_used"] == s0["players used"]
    # Single-word metrics
    assert r0["played"] == s0["played"]
    assert r0["wins"] == s0["wins"]
    assert r0["odds"] == s0["odds"]
    # raw_payload is the serialised position object
    assert json.loads(r0["raw_payload"])["teamNickname"] == nick0


def test_standing_rows_position_falls_back_to_index(ladder_payload):
    """The upstream has no `position` key → ladder_position == 1-based index."""
    rows = _extract_standing_rows(
        ladder_payload,
        key=_LADDER_KEY,
        competition=111,
        season=2026,
        round_no=12,
        team_map={},
    )
    assert [r["ladder_position"] for r in rows[:3]] == [1, 2, 3]


def test_standing_rows_unresolved_team_id_is_none(ladder_payload):
    """A nickname absent from team_map yields team_id None (row still emitted)."""
    rows = _extract_standing_rows(
        ladder_payload,
        key=_LADDER_KEY,
        competition=111,
        season=2026,
        round_no=12,
        team_map={},  # nothing resolves
    )
    assert len(rows) == len(ladder_payload["positions"])
    assert all(r["team_id"] is None for r in rows)
    assert all(r["nrlcom_team_nickname"] for r in rows)  # nickname still carried


# ── _casualty_to_row ──────────────────────────────────────────────────────

def test_casualty_row_maps_fields(casualty_payload):
    c = casualty_payload["casualties"][0]
    team_map = {c["teamNickname"].lower(): _PANTHERS}
    row = _casualty_to_row(c, team_map=team_map, people_lookup={})
    assert row is not None
    assert row["canonical"] == f"{c['firstName']} {c['lastName']}".strip()
    assert row["team_nickname"] == c["teamNickname"]
    assert row["team_id"] == _PANTHERS
    assert row["body_part"] == c["injury"]
    assert row["url"] == c["url"]
    assert row["expected_return_text"] == c["expectedReturn"]
    assert row["key_today"] == (row["canonical"].lower(), c["teamNickname"].lower())
    # "Round N" expected-return text parses to the integer round
    if "Round" in (c["expectedReturn"] or ""):
        assert isinstance(row["expected_return_round"], int)


def test_casualty_row_resolves_person_via_lookup(casualty_payload):
    c = casualty_payload["casualties"][0]
    canonical = f"{c['firstName']} {c['lastName']}".strip()
    nick = c["teamNickname"]
    people_lookup = {(canonical.lower(), nick.lower()): "person-uuid-xyz"}
    row = _casualty_to_row(c, team_map={}, people_lookup=people_lookup)
    assert row["person_id"] == "person-uuid-xyz"
    assert row["team_id"] is None  # empty team_map → unresolved, still a row


def test_casualty_row_skip_no_name():
    c = {"firstName": "", "lastName": "", "teamNickname": "Broncos",
         "injury": "Knee", "expectedReturn": "Round 13", "url": None,
         "imageUrl": None, "theme": None}
    assert _casualty_to_row(c, team_map={}, people_lookup={}) is None


def test_casualty_row_skip_no_team():
    c = {"firstName": "Grant", "lastName": "Anderson", "teamNickname": "",
         "injury": "Knee", "expectedReturn": "Round 13", "url": None,
         "imageUrl": None, "theme": None}
    assert _casualty_to_row(c, team_map={}, people_lookup={}) is None


# ── _bucket_status ────────────────────────────────────────────────────────

def test_bucket_status_round_gap_buckets():
    assert _bucket_status("Round 13", current_round=12) == "1_week"   # gap 1
    assert _bucket_status("Round 15", current_round=12) == "2_4_weeks"  # gap 3
    assert _bucket_status("Round 20", current_round=12) == "4_8_weeks"  # gap 8
    # Round-N with no known current round → assume mid-term
    assert _bucket_status("Round 13", current_round=None) == "2_4_weeks"


def test_bucket_status_keyword_buckets():
    assert _bucket_status("Indefinite") == "indefinite"
    assert _bucket_status("TBC") == "indefinite"
    assert _bucket_status("Out for season") == "season"
    assert _bucket_status("Training") == "training"
    assert _bucket_status("Test") == "test"
    assert _bucket_status("") == "indefinite"  # empty → indefinite default
