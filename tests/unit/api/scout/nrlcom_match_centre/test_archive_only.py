"""Phase 5: `archive_only=true` mode on the nrl.com match-centre route.

Different shape from the single-archive routes (draw / ladder / stats):
the match-centre walker fetches the draw first, then per-fixture loops
through `fetch_match_centre`. The per-match strict-parse is already
non-aborting (errors go into `validation_failures[]`); `archive_only=True`
makes it skipped entirely.

Three cases:
  1. archive_only=True + one fixture with a drift payload → response
     `validated:false, validation_skipped:true, ok:true, matches_archived=1`;
     `validation_failures` stays empty (no per-match parse ran).
  2. archive_only=True + valid payload → also `validated:false,
     validation_skipped:true` (the flag is unconditional).
  3. archive_only=False (default) + valid payload → existing behaviour:
     no `validation_skipped` key; `validation_failures` empty because
     the payload parses; matches_archived=1.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.scout.nrlcom_match_centre.routes import run_nrlcom_match_centre


class _FakeRun:
    def __init__(self, run_id: str = "scout-test-run") -> None:
        self.run_id = run_id
        self.detail: dict[str, Any] = {}
        self.completed = False
        self.failed = False

    def complete(self, *, summary_text: str) -> None:
        self.completed = True

    def fail(self, exc: Exception, *, summary_text: str) -> None:
        self.failed = True


@pytest.fixture(scope="module")
def canonical_match_centre(fixtures_dir: Path) -> dict:
    """The canonical (FullTime) match-centre response."""
    path = fixtures_dir / "scout" / "nrlcom_match_centre" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def drift_match_centre(canonical_match_centre: dict) -> dict:
    """A match-centre payload mutated to fail strict-parse."""
    bad = json.loads(json.dumps(canonical_match_centre))
    bad["loot_boxes"] = {"unexpected": True}
    return bad


@pytest.fixture
def single_fixture_draw() -> dict:
    """Synthetic 1-fixture draw payload so the walker only loops once."""
    return {
        "selectedRoundId": 12,
        "fixtures": [
            {
                "matchCentreUrl": "/draw/nrl-premiership/2026/round-12/raiders-v-dolphins/",
            }
        ],
    }


def _patched_walk(*, draw_payload: dict, match_payload: dict, archive_only: bool):
    fake_run = _FakeRun()
    with patch(
        "app.scout.nrlcom_match_centre.routes.fetch_draw",
        return_value=draw_payload,
    ), patch(
        "app.scout.nrlcom_match_centre.routes.fetch_match_centre",
        return_value=match_payload,
    ), patch(
        "app.scout.nrlcom_match_centre.routes.archive_response",
        return_value="scout/nrlcom/match-centre/111/2026/round-12/raiders-v-dolphins.json",
    ), patch(
        "app.scout.nrlcom_match_centre.routes.start_deterministic_run",
        return_value=fake_run,
    ), patch(
        # Skip the per-match 1-second rate-limit sleep in unit tests
        "app.scout.nrlcom_match_centre.routes.time.sleep",
        return_value=None,
    ):
        response = run_nrlcom_match_centre(
            db=MagicMock(),
            competition=111,
            season=2026,
            round=12,
            archive_only=archive_only,
        )
    return response, fake_run


def test_archive_only_true_skips_per_match_validation_on_drift(
    single_fixture_draw, drift_match_centre,
):
    """Drift on the per-match payload + archive_only=True → archived but not validated."""
    response, fake_run = _patched_walk(
        draw_payload=single_fixture_draw,
        match_payload=drift_match_centre,
        archive_only=True,
    )
    assert response["ok"] is True
    assert response["validated"] is False
    assert response["validation_skipped"] is True
    assert response["matches_archived"] == 1
    # The per-match strict-parse was skipped — no entries in validation_failures.
    assert response["validation_failures"] == []
    assert fake_run.completed


def test_archive_only_true_modern_payload_still_archives(
    single_fixture_draw, canonical_match_centre,
):
    """Valid payload + archive_only=True → still skipped (flag is unconditional)."""
    response, fake_run = _patched_walk(
        draw_payload=single_fixture_draw,
        match_payload=canonical_match_centre,
        archive_only=True,
    )
    assert response["ok"] is True
    assert response["validated"] is False
    assert response["validation_skipped"] is True
    assert response["matches_archived"] == 1
    assert response["validation_failures"] == []
    assert fake_run.completed


def test_archive_only_default_false_unchanged_modern(
    single_fixture_draw, canonical_match_centre,
):
    """Default path: valid match payload, no archive_only — existing behaviour."""
    response, fake_run = _patched_walk(
        draw_payload=single_fixture_draw,
        match_payload=canonical_match_centre,
        archive_only=False,
    )
    assert response["ok"] is True
    assert "validated" not in response or response.get("validated") is None
    assert "validation_skipped" not in response
    assert response["matches_archived"] == 1
    # The valid payload parses → no per-match validation failures.
    assert response["validation_failures"] == []
    assert fake_run.completed
