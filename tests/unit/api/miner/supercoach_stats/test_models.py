"""Unit tests for SuperCoach stats strict Pydantic model (D8 drift contract).

The fixture is a raw jqGrid response (~20 rows, 95 fields each), so the
tests also exercise the extraction layer in
`app.miner.supercoach_stats.fetcher.extract_rows`. If the upstream
renames or removes a column listed in `JQGRID_COLUMN_MAP`, extraction
returns `None` for that DB column and the strict model raises — that's
the D8 drift signal.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from app.miner.supercoach_stats.fetcher import extract_rows
from app.miner.supercoach_stats.models import SuperCoachPlayerStats
from pydantic import ValidationError


@pytest.fixture(scope="module")
def raw_response(fixtures_dir: Path) -> dict:
    """The canonical raw jqGrid response (envelope + rows)."""
    path = fixtures_dir / "miner" / "supercoach_stats" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def raw_rows(raw_response) -> list[dict]:
    return raw_response["rows"]


@pytest.fixture(scope="module")
def extracted(raw_rows) -> list[dict]:
    return extract_rows(raw_rows)


def test_extraction_produces_one_dict_per_input_row(raw_rows, extracted):
    """Sanity: every raw row that has a name produces one extracted row."""
    rows_with_name = sum(1 for r in raw_rows if str(r.get("Name2", "")).strip() or str(r.get("Name", "")).strip())
    assert len(extracted) == rows_with_name


def test_canonical_fixture_parses_strictly(extracted):
    """Every extracted row parses cleanly through SuperCoachPlayerStats.

    Catches: a Pydantic model that doesn't match the extracted shape
    (missing field, wrong type, accidentally non-nullable required).
    """
    parsed = [SuperCoachPlayerStats.model_validate(p) for p in extracted]
    assert len(parsed) == len(extracted)
    # Sanity: identity always populated
    assert all(p.player_id > 0 for p in parsed)
    assert all(p.player_name for p in parsed)
    assert all(p.team for p in parsed)


def test_unknown_field_on_extracted_row_raises(extracted):
    """Drift: an unknown field on the extracted shape trips the model.

    Tests that we'd notice if extract_rows started producing a field
    SuperCoachPlayerStats doesn't model (e.g. a new column was added to
    JQGRID_COLUMN_MAP without updating the model).
    """
    bad = copy.deepcopy(extracted[0])
    bad["is_byzantine_winger"] = True  # invented field
    with pytest.raises(ValidationError) as excinfo:
        SuperCoachPlayerStats.model_validate(bad)
    assert "is_byzantine_winger" in str(excinfo.value)


def test_missing_required_field_raises(extracted):
    """Drift: dropping a required identity field fails parsing.

    Catches the case where SuperCoach renames `Name`/`Name2`/`Team`/`Posn1`
    and our extraction returns "" / drops the field entirely.
    """
    bad = copy.deepcopy(extracted[0])
    del bad["player_id"]
    with pytest.raises(ValidationError) as excinfo:
        SuperCoachPlayerStats.model_validate(bad)
    assert "player_id" in str(excinfo.value)
