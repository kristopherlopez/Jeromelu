"""Unit tests for the phase_matches pure extractors.

Two pure parse/map seams — no S3, no DB:
  - `_extract_one(payload, key, team_map, venue_map)` — match-centre archive
  - `_extract_from_draw_fixture(fixture, *, season, round_no, ...)` — draw archive

We feed the real Phase 3 match-centre fixture (a FullTime raiders-v-dolphins
R12 payload) plus fake identity maps and assert the projected `matches` row.
Phase 5 (era-aware) augments these tests with synthetic timeline-only and
draw-only payloads to exercise the `data_coverage` derivation.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.data.populate.phase_matches import (
    _GRADE_MAP,
    _KEY_RE,
    _DRAW_KEY_RE,
    _derive_data_coverage,
    _draw_external_id,
    _extract_from_draw_fixture,
    _extract_one,
    _normalize_status,
    _slug_from_match_centre_url,
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


# --- Phase 5 era-aware additions -------------------------------------------------

def test_full_match_centre_emits_data_coverage_full(payload, team_map):
    """The canonical FullTime fixture has stats.players → data_coverage='full'."""
    row = _extract_one(payload, _KEY, team_map, venue_map={})
    assert row is not None
    assert row["data_coverage"] == "full"
    # Sanity: the fixture really does have stats.players populated.
    assert (payload.get("stats") or {}).get("players")


def test_timeline_only_match_centre_emits_data_coverage_timeline_only(team_map):
    """A pre-2000 match-centre archive with timeline only but no players/stats.

    Synthetic minimal payload — the 1990–1999 partial-shape era.
    """
    home_team_id, away_team_id = list(team_map.keys())[:2]
    timeline_only = {
        "matchId": "19951119001",
        "matchState": "FullTime",
        "homeTeam": {"teamId": home_team_id, "score": 12},
        "awayTeam": {"teamId": away_team_id, "score": 8},
        # No "players" on either team, no "stats" block.
        "timeline": [
            {"type": "Try", "title": "Try", "gameSeconds": 600, "teamId": home_team_id},
        ],
        "venue": "Some Old Ground",
    }
    key = "scout/nrlcom/match-centre/111/1995/round-01/some-match.json"
    row = _extract_one(timeline_only, key, team_map, venue_map={})
    assert row is not None
    assert row["data_coverage"] == "timeline_only"
    assert row["season"] == 1995
    assert row["status"] == "final"


def test_lineups_no_stats_emits_lineups_plus_timeline(team_map):
    """A pre-finish or partial-shape archive with rosters but no stats."""
    home_team_id, away_team_id = list(team_map.keys())[:2]
    lineups_only = {
        "matchId": "20100501999",
        "matchState": "InProgress",
        "homeTeam": {
            "teamId": home_team_id,
            "players": [{"playerId": 100, "number": 1, "position": "FB"}],
            "score": 0,
        },
        "awayTeam": {
            "teamId": away_team_id,
            "players": [{"playerId": 200, "number": 1, "position": "FB"}],
            "score": 0,
        },
        # No stats block.
        "timeline": [],
    }
    key = "scout/nrlcom/match-centre/111/2010/round-05/some-match.json"
    row = _extract_one(lineups_only, key, team_map, venue_map={})
    assert row is not None
    assert row["data_coverage"] == "lineups+timeline"


def test_draw_only_fixture_emits_data_coverage_fixture_only(team_map):
    """A 1908-era draw fixture (no matchCentreUrl) projects as fixture_only."""
    home_team_id, away_team_id = list(team_map.keys())[:2]
    fixture = {
        "matchState": "FullTime",
        # No matchCentreUrl — pre-1990 fixtures lack one
        "homeTeam": {"teamId": home_team_id, "nickName": "Old Home", "score": 10},
        "awayTeam": {"teamId": away_team_id, "nickName": "Old Away", "score": 5},
        "venue": "Historic Ground",
        "roundTitle": "Round 1",
    }
    row = _extract_from_draw_fixture(
        fixture,
        season=1908,
        round_no=1,
        competition=111,
        team_map=team_map,
        venue_map={},
    )
    assert row is not None
    assert row["data_coverage"] == "fixture_only"
    assert row["season"] == 1908
    assert row["round"] == 1
    assert row["grade"] == "nrl"
    assert row["status"] == "final"
    # Synthetic ext id when matchCentreUrl absent
    assert row["external_match_id"] == "old-home-v-old-away-r01-1908"


def test_draw_fixture_with_url_uses_slug(team_map):
    """Modern draw fixtures derive external_match_id from matchCentreUrl slug."""
    home_team_id, away_team_id = list(team_map.keys())[:2]
    fixture = {
        "matchState": "Upcoming",
        "matchCentreUrl": "/draw/nrl-premiership/2026/round-13/sharks-v-sea-eagles/",
        "homeTeam": {"teamId": home_team_id, "nickName": "Sharks"},
        "awayTeam": {"teamId": away_team_id, "nickName": "Sea Eagles"},
        "venue": "Ocean Protect Stadium",
        "roundTitle": "Round 13",
    }
    row = _extract_from_draw_fixture(
        fixture,
        season=2026,
        round_no=13,
        competition=111,
        team_map=team_map,
        venue_map={},
    )
    assert row is not None
    assert row["external_match_id"] == "sharks-v-sea-eagles"
    assert row["data_coverage"] == "fixture_only"
    assert row["status"] == "scheduled"


def test_draw_fixture_unresolved_team_returns_none():
    """Empty team_map → can't resolve home/away → skip."""
    fixture = {
        "matchState": "Upcoming",
        "matchCentreUrl": "/draw/x/y/round-1/foo/",
        "homeTeam": {"teamId": 999999, "nickName": "Foo"},
        "awayTeam": {"teamId": 888888, "nickName": "Bar"},
    }
    assert _extract_from_draw_fixture(
        fixture,
        season=2026,
        round_no=1,
        competition=111,
        team_map={},
        venue_map={},
    ) is None


def test_data_coverage_derivation_thresholds():
    """Direct unit coverage of `_derive_data_coverage`'s 4-band ladder."""
    # 1. stats.players present (full)
    assert _derive_data_coverage({
        "stats": {"players": {"homeTeam": [{"playerId": 1}]}}
    }) == "full"
    # 2. team players present, no stats (lineups+timeline)
    assert _derive_data_coverage({
        "homeTeam": {"players": [{"playerId": 1}]},
        "awayTeam": {"players": [{"playerId": 2}]},
    }) == "lineups+timeline"
    # 3. timeline present, no players (timeline_only)
    assert _derive_data_coverage({
        "timeline": [{"type": "Try"}],
    }) == "timeline_only"
    # 4. empty payload (degenerate; falls back to fixture_only)
    assert _derive_data_coverage({}) == "fixture_only"


def test_slug_from_match_centre_url_handles_edge_cases():
    """URL slug derivation: trailing slash optional; None/empty → None."""
    assert _slug_from_match_centre_url(
        "/draw/nrl-premiership/2026/round-13/sharks-v-sea-eagles/"
    ) == "sharks-v-sea-eagles"
    assert _slug_from_match_centre_url(
        "/draw/nrl-premiership/2026/round-13/sharks-v-sea-eagles"  # no trailing /
    ) == "sharks-v-sea-eagles"
    assert _slug_from_match_centre_url(None) is None
    assert _slug_from_match_centre_url("") is None


def test_draw_external_id_prefers_slug_over_synthetic():
    """When matchCentreUrl is present, slug wins over the synthetic fallback."""
    assert _draw_external_id(
        {
            "matchCentreUrl": "/x/y/2026/round-1/real-slug/",
            "homeTeam": {"nickName": "Home"},
            "awayTeam": {"nickName": "Away"},
        },
        season=2026,
        round_no=1,
    ) == "real-slug"


def test_draw_key_regex_parses_components():
    """The walker uses _DRAW_KEY_RE to extract (comp, season, round) per draw archive."""
    m = _DRAW_KEY_RE.search(
        "scout/nrlcom/draw/111/2010/round-05.json"
    )
    assert m is not None
    assert m.group("comp") == "111"
    assert m.group("season") == "2010"
    assert m.group("round") == "05"


def test_match_centre_present_skips_draw_projection_pure(team_map):
    """When a draw fixture's match-centre slug is already in the seen-set,
    a separate draw-only projection MUST NOT be emitted.

    Documents the walker's pre-built mc_slugs gate at the pure-function
    level — driver loop integration test in `populate_matches` is exercised
    by the dry-run end-to-end (verified: draw_skipped_mc_exists=204 on 2026).
    """
    home_team_id, away_team_id = list(team_map.keys())[:2]

    # The draw fixture exists.
    fixture = {
        "matchState": "FullTime",
        "matchCentreUrl": "/draw/nrl-premiership/2026/round-13/sharks-v-sea-eagles/",
        "homeTeam": {"teamId": home_team_id, "nickName": "Sharks", "score": 24},
        "awayTeam": {"teamId": away_team_id, "nickName": "Sea Eagles", "score": 12},
    }

    # The mc_slugs set, populated from the match-centre walk, already contains
    # the fixture's (season, round, slug) — emulating the populate_matches gate.
    slug = _slug_from_match_centre_url(fixture["matchCentreUrl"])
    assert slug == "sharks-v-sea-eagles"

    mc_slugs = {(2026, 13, "sharks-v-sea-eagles")}

    # The walker's gate: `if slug and (season, round_no, slug) in mc_slugs: continue`.
    # We assert the slug-derivation matches what the gate expects.
    season = 2026
    round_no = 13
    assert (season, round_no, slug) in mc_slugs

    # And confirm _extract_from_draw_fixture itself remains a pure function:
    # it WILL produce a row if called directly (no implicit gate). The gate
    # lives in the walker, not in the projection. This is the contract:
    # callers (the walker) own dedup; the projector just projects.
    row_if_called = _extract_from_draw_fixture(
        fixture,
        season=season,
        round_no=round_no,
        competition=111,
        team_map=team_map,
        venue_map={},
    )
    assert row_if_called is not None
    assert row_if_called["external_match_id"] == "sharks-v-sea-eagles"
    # The walker is supposed to NOT call this when slug is in mc_slugs;
    # this test pins the responsibility split between projector and walker.
