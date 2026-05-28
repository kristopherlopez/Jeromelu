"""Phase 5: `archive_only=true` mode on the nrl.com /stats/data route.

Mirrors `tests/unit/api/scout/nrlcom_draw/test_archive_only.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from app.scout.nrlcom_stats.routes import run_nrlcom_stats


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
def canonical_payload(fixtures_dir: Path) -> dict:
    path = fixtures_dir / "scout" / "nrlcom_stats" / "canonical_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def drift_payload(canonical_payload: dict) -> dict:
    bad = json.loads(json.dumps(canonical_payload))
    bad["loot_boxes"] = {"unexpected": True}
    return bad


def _patched_run(fixture_payload: dict, *, archive_only: bool):
    fake_run = _FakeRun()
    with (
        patch(
            "app.scout.nrlcom_stats.routes.fetch_stats",
            return_value=fixture_payload,
        ),
        patch(
            "app.scout.nrlcom_stats.routes.archive_response",
            return_value="scout/nrlcom/stats/111/2026.json",
        ),
        patch(
            "app.scout.nrlcom_stats.routes.start_deterministic_run",
            return_value=fake_run,
        ),
    ):
        response = run_nrlcom_stats(
            db=MagicMock(),
            competition=111,
            season=2026,
            archive_only=archive_only,
        )
    return response, fake_run


def test_archive_only_true_skips_validation_on_drift(drift_payload):
    response, fake_run = _patched_run(drift_payload, archive_only=True)
    assert response["ok"] is True
    assert response["validated"] is False
    assert response["validation_skipped"] is True
    assert fake_run.completed
    assert not fake_run.failed


def test_archive_only_true_modern_payload_still_archives(canonical_payload):
    response, fake_run = _patched_run(canonical_payload, archive_only=True)
    assert response["ok"] is True
    assert response["validated"] is False
    assert response["validation_skipped"] is True
    assert fake_run.completed


def test_archive_only_default_false_unchanged_modern(canonical_payload):
    response, fake_run = _patched_run(canonical_payload, archive_only=False)
    assert response["ok"] is True
    assert response["validated"] is True
    assert "validation_skipped" not in response
    assert fake_run.completed
