"""Phase 5: unit tests for `_extract_player_round_rows` (the new
SC stats DB extractor's pure projection seam).

Pure-function tests over the (payload → rows + failures) projection — no
S3, no DB. Mirrors the Phase 4.5 `_extract_leader_rows` pattern. The
projection takes the S3 archive payload (`{season, round, rows: [<raw
jqGrid>]}`) and emits dicts ready for the `player_rounds` UPSERT.

Three required cases per task spec, plus a fixture-shaped round-trip:
  1. Canonical archive round-trip — 3 known raw rows project to 3 rows
     with the full identity + base + STAT_DB_COLUMNS keyset and the
     correct season/round.
  2. Empty rows → empty output.
  3. Per-row strict-parse failure does NOT abort — bad row recorded in
     `failures`, good rows still emitted.
"""

from __future__ import annotations

from typing import Any

import pytest

from jeromelu_shared.scraping.nrl import STAT_DB_COLUMNS
from scripts.data.populate.phase_player_rounds import _extract_player_round_rows


_IDENTITY_KEYS = {"player_id", "player_name", "team", "position", "round", "season"}
_BASE_KEYS = {"score", "price", "breakeven", "minutes"}
_EXPECTED_KEYS = _IDENTITY_KEYS | _BASE_KEYS | set(STAT_DB_COLUMNS)


def _make_raw_row(name: str, team: str, posn: str = "FB", **overrides: Any) -> dict[str, Any]:
    """Build a synthetic jqGrid raw row that extract_rows can process."""
    row = {
        "Name2": name,
        "Team": team,
        "Posn1": posn,
        "Rd": "12",
        "Price": "500000",
        "BE": "30",
        "Score": "50",
        "Time": "80",
        "Base": "20",
        "Attack": "10",
        "Playmaking": "5",
        "Power": "10",
        "Negative": "-5",
    }
    row.update(overrides)
    return row


def test_canonical_archive_round_trip():
    """3 valid rows → 3 dicts with the full _EXPECTED_KEYS keyset."""
    payload = {
        "season": 2026,
        "round": 12,
        "rows": [
            _make_raw_row("Player One", "Storm", "FB"),
            _make_raw_row("Player Two", "Panthers", "HK"),
            _make_raw_row("Player Three", "Eels", "MID"),
        ],
    }
    rows, failures = _extract_player_round_rows(payload, season=2026, round_no=12)
    assert len(rows) == 3
    assert failures == []
    # Every row has the full keyset (identity + base + STAT_DB_COLUMNS).
    for r in rows:
        assert _EXPECTED_KEYS.issubset(r.keys()), (
            f"missing keys: {_EXPECTED_KEYS - r.keys()}"
        )
        # season + round pinned from the key path
        assert r["season"] == 2026
        assert r["round"] == 12
        # base-block scoring fields parsed
        assert r["score"] == 50
        assert r["price"] == 500000
        assert r["breakeven"] == 30
        assert r["minutes"] == 80
        # player_id is deterministic from name+team (positive int)
        assert isinstance(r["player_id"], int)
        assert r["player_id"] > 0


def test_empty_rows_returns_empty():
    """payload['rows'] = [] → ([], [])."""
    payload = {"season": 2026, "round": 1, "rows": []}
    rows, failures = _extract_player_round_rows(payload, season=2026, round_no=1)
    assert rows == []
    assert failures == []


def test_strict_parse_failure_per_row_does_not_abort(monkeypatch):
    """Inject one bad row in 3 — the extractor records it in failures and
    continues; the other 2 are still emitted.

    We simulate the strict-parse failure by patching `extract_rows` (it
    runs FIRST and produces the dict shape `SuperCoachPlayerStats` parses);
    here we surgically introduce a row with a wrong type for `player_id`
    so model_validate raises ValidationError on that one row only.
    """
    # Use the real extract_rows so the synthetic raw rows produce proper
    # extracted dicts; then mutate one of them before strict-parse via a
    # post-extract patch.
    payload = {
        "season": 2026,
        "round": 12,
        "rows": [
            _make_raw_row("Good Player One", "Storm"),
            _make_raw_row("Bad Player", "Panthers"),
            _make_raw_row("Good Player Two", "Eels"),
        ],
    }
    # Patch extract_rows to corrupt the middle row's player_id (str where int required).
    from scripts.data.populate import phase_player_rounds as mod
    real_extract = mod.extract_rows

    def corrupting_extract(raw_rows):
        out = real_extract(raw_rows)
        if len(out) >= 2:
            out[1]["player_id"] = "not-an-int"  # type drift → ValidationError
        return out

    monkeypatch.setattr(mod, "extract_rows", corrupting_extract)

    rows, failures = _extract_player_round_rows(payload, season=2026, round_no=12)
    assert len(rows) == 2, f"expected 2 good rows, got {len(rows)}: {rows}"
    assert len(failures) == 1
    assert failures[0]["player_name_hint"] == "Bad Player"
    assert "player_id" in failures[0]["error"]
    # Good rows are emitted with correct identity
    assert rows[0]["player_name"] == "Good Player One"
    assert rows[1]["player_name"] == "Good Player Two"
    assert all(r["season"] == 2026 and r["round"] == 12 for r in rows)


def test_season_round_from_key_path_override_payload():
    """Season + round_no kwargs are authoritative even if payload disagrees.

    Defensive — the S3 key is the source of truth (matches the route's
    archive path); the payload's own season/round are double-checked but
    not load-bearing.
    """
    payload = {
        "season": 1999,  # wrong on purpose
        "round": 99,     # wrong on purpose
        "rows": [_make_raw_row("Test", "Storm")],
    }
    rows, _ = _extract_player_round_rows(payload, season=2026, round_no=5)
    assert len(rows) == 1
    assert rows[0]["season"] == 2026  # kwarg won
    assert rows[0]["round"] == 5
