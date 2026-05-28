"""Phase 5: `archive_only=true` mode on the nrl.com /draw/data route.

Three cases:
  1. archive_only=True + drift payload → response carries `validated:false,
     validation_skipped:true, ok:true`; NO HTTPException raised. The S3
     archive still happens (capture preserved).
  2. archive_only=True + valid payload → response also carries
     `validated:false, validation_skipped:true` — the flag is unconditional;
     the strict-parse is skipped even when it would have passed.
  3. archive_only=False (default) + canonical payload → existing behaviour:
     `validated:true, ok:true`, NO `validation_skipped` key.

We patch the module-level imports (`fetch_draw`, `archive_response`,
`start_deterministic_run`) and pass a stub Session — the route's logic is
pure once those are mocked.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.scout.nrlcom_draw.routes import run_nrlcom_draw


class _FakeRun:
    """Minimal stand-in for DeterministicScoutRun (records .complete/.fail)."""

    def __init__(self, run_id: str = "scout-test-run") -> None:
        self.run_id = run_id
        self.detail: dict[str, Any] = {}
        self.completed: bool = False
        self.failed: bool = False
        self.complete_summary: str | None = None
        self.fail_summary: str | None = None

    def complete(self, *, summary_text: str) -> None:
        self.completed = True
        self.complete_summary = summary_text

    def fail(self, exc: Exception, *, summary_text: str) -> None:
        self.failed = True
        self.fail_summary = summary_text


@pytest.fixture(scope="module")
def canonical_payload(fixtures_dir: Path) -> dict:
    """The canonical /draw/data response fixture (passes NrlcomDraw strict-parse)."""
    path = fixtures_dir / "scout" / "nrlcom_draw" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def drift_payload(canonical_payload: dict) -> dict:
    """A canonical payload mutated to fail strict-parse (extra unknown top-level field)."""
    bad = json.loads(json.dumps(canonical_payload))
    bad["loot_boxes"] = {"unexpected": True}
    return bad


def _patched_run(fixture_payload: dict, *, archive_only: bool):
    """Run the route's pure function with module-level deps mocked."""
    fake_run = _FakeRun()
    with patch(
        "app.scout.nrlcom_draw.routes.fetch_draw",
        return_value=fixture_payload,
    ), patch(
        "app.scout.nrlcom_draw.routes.archive_response",
        return_value="scout/nrlcom/draw/111/2026/round-13.json",
    ), patch(
        "app.scout.nrlcom_draw.routes.start_deterministic_run",
        return_value=fake_run,
    ):
        response = run_nrlcom_draw(
            db=MagicMock(),
            competition=111,
            season=2026,
            round=None,
            archive_only=archive_only,
        )
    return response, fake_run


def test_archive_only_true_skips_validation_on_drift(drift_payload):
    """Drift payload + archive_only=True → 200 OK with validation_skipped, NOT 500."""
    response, fake_run = _patched_run(drift_payload, archive_only=True)
    assert response["ok"] is True
    assert response["validated"] is False
    assert response["validation_skipped"] is True
    assert "s3_archive_key" in response
    assert fake_run.completed
    assert not fake_run.failed


def test_archive_only_true_modern_payload_still_archives(canonical_payload):
    """Valid payload + archive_only=True → still skips validation (flag is unconditional)."""
    response, fake_run = _patched_run(canonical_payload, archive_only=True)
    assert response["ok"] is True
    assert response["validated"] is False
    assert response["validation_skipped"] is True
    assert "s3_archive_key" in response
    assert fake_run.completed


def test_archive_only_default_false_unchanged_modern(canonical_payload):
    """Default path (archive_only=False) with valid payload — existing behaviour."""
    response, fake_run = _patched_run(canonical_payload, archive_only=False)
    assert response["ok"] is True
    assert response["validated"] is True
    assert "validation_skipped" not in response  # regression check
    assert "s3_archive_key" in response
    assert fake_run.completed


def test_archive_response_called_under_archive_only(drift_payload):
    """Capture is preserved even on drift in archive_only mode."""
    with patch(
        "app.scout.nrlcom_draw.routes.fetch_draw",
        return_value=drift_payload,
    ), patch(
        "app.scout.nrlcom_draw.routes.archive_response",
        return_value="scout/nrlcom/draw/111/1995/round-01.json",
    ) as mock_archive, patch(
        "app.scout.nrlcom_draw.routes.start_deterministic_run",
        return_value=_FakeRun(),
    ):
        run_nrlcom_draw(
            db=MagicMock(),
            competition=111,
            season=1995,
            round=1,
            archive_only=True,
        )
    # archive_response was called exactly once with the drift payload — capture preserved
    assert mock_archive.call_count == 1
    call_kwargs = mock_archive.call_args.kwargs
    assert call_kwargs["source"] == "nrlcom"
    assert call_kwargs["pipeline"] == "draw"
