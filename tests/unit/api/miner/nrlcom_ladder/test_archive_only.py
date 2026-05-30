"""Phase 5: `archive_only=true` mode on the nrl.com /ladder/data route.

Mirrors `tests/unit/api/miner/nrlcom_draw/test_archive_only.py` — see that
file for the design rationale and the FakeRun stand-in.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from app.miner.nrlcom_ladder.routes import run_nrlcom_ladder


class _FakeRun:
    def __init__(self, run_id: str = "miner-test-run") -> None:
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
    path = fixtures_dir / "miner" / "nrlcom_ladder" / "canonical_response.json"
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
            "app.miner.nrlcom_ladder.routes.fetch_ladder",
            return_value=fixture_payload,
        ),
        patch(
            "app.miner.nrlcom_ladder.routes.archive_response",
            return_value="miner/nrlcom/ladder/111/2026/round-12.json",
        ),
        patch(
            "app.miner.nrlcom_ladder.routes.start_deterministic_run",
            return_value=fake_run,
        ),
    ):
        response = run_nrlcom_ladder(
            db=MagicMock(),
            competition=111,
            season=2026,
            round=None,
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
