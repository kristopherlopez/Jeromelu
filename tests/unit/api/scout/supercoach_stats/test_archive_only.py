"""Phase 5: `archive_only=true` mode on the SuperCoach stats route.

The SC stats route is special vs the 4 nrl.com routes (TASK-38): it writes
to DB inline via `_upsert_player_rounds`. archive_only=True must skip BOTH
the strict-parse AND the inline DB upsert. The S3 archive still happens
(it runs before the parse).

Four cases:
  1. archive_only=True + drift-ish payload → response carries
     `validated:false, validation_skipped:true, upserted:0, fetched:0`;
     `_upsert_player_rounds` is NOT called (verified by mock-spy).
  2. archive_only=True + valid payload → same shape: validation still
     skipped, upsert still skipped (flag is unconditional).
  3. archive_only=False (default) + valid payload → existing behaviour:
     no `validation_skipped` key, `_upsert_player_rounds` IS called.
  4. archive_only=True + valid payload → assert `archive_response` was
     called (capture is preserved even with the strict-parse skip).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.scout.supercoach_stats.routes import run_supercoach_stats


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


@pytest.fixture
def valid_raw_rows() -> list[dict[str, Any]]:
    """Tiny synthetic SC raw rows that extract_rows() can process cleanly."""
    return [
        {
            "Name2": "Test Player",
            "Team": "Storm",
            "Posn1": "FB",
            "Rd": "12",
            "Price": "500000",
            "BE": "30",
            "Score": "50",
            "Time": "80",
        }
    ]


def _patched_run(raw_rows: list[dict[str, Any]], *, archive_only: bool):
    """Run the SC stats route with module-level deps mocked."""
    fake_run = _FakeRun()
    with patch(
        "app.scout.supercoach_stats.routes.fetch_stats_raw",
        return_value=raw_rows,
    ), patch(
        "app.scout.supercoach_stats.routes.archive_response",
        return_value="scout/nrlsupercoachstats/stats/2026/round-12.json",
    ) as mock_archive, patch(
        "app.scout.supercoach_stats.routes.start_deterministic_run",
        return_value=fake_run,
    ), patch(
        "app.scout.supercoach_stats.routes._upsert_player_rounds",
        return_value=1,
    ) as mock_upsert:
        response = run_supercoach_stats(
            db=MagicMock(),
            season=2026,
            round=12,
            archive_only=archive_only,
        )
    return response, fake_run, mock_archive, mock_upsert


def test_archive_only_true_skips_validation_and_upsert(valid_raw_rows):
    """archive_only=True skips BOTH strict-parse and inline DB upsert."""
    response, fake_run, mock_archive, mock_upsert = _patched_run(
        valid_raw_rows, archive_only=True,
    )
    assert response["ok"] is True
    assert response["validated"] is False
    assert response["validation_skipped"] is True
    assert response["fetched"] == 0
    assert response["upserted"] == 0
    # Inline DB upsert was NOT called.
    assert mock_upsert.call_count == 0
    # S3 archive WAS called — capture preserved.
    assert mock_archive.call_count == 1
    assert fake_run.completed
    assert not fake_run.failed


def test_archive_only_true_valid_payload_still_skips(valid_raw_rows):
    """archive_only=True is unconditional — valid payload also skips."""
    response, fake_run, mock_archive, mock_upsert = _patched_run(
        valid_raw_rows, archive_only=True,
    )
    assert response["validated"] is False
    assert response["validation_skipped"] is True
    assert mock_upsert.call_count == 0
    assert fake_run.completed


def test_archive_only_default_false_runs_upsert(valid_raw_rows):
    """Default path: validation runs, DB upsert is called."""
    response, fake_run, mock_archive, mock_upsert = _patched_run(
        valid_raw_rows, archive_only=False,
    )
    assert response["ok"] is True
    # No validation_skipped key on the default path (regression check).
    assert "validation_skipped" not in response
    assert "validated" not in response  # SC stats route doesn't set validated:true on default path
    assert response["fetched"] == 1
    assert response["upserted"] == 1
    # Inline DB upsert WAS called.
    assert mock_upsert.call_count == 1
    assert fake_run.completed


def test_archive_response_called_under_archive_only(valid_raw_rows):
    """S3 capture happens even when validate + upsert are skipped."""
    _, _, mock_archive, _ = _patched_run(valid_raw_rows, archive_only=True)
    assert mock_archive.call_count == 1
    call_kwargs = mock_archive.call_args.kwargs
    assert call_kwargs["source"] == "nrlsupercoachstats"
    assert call_kwargs["pipeline"] == "stats"
    assert "rows" in call_kwargs["payload"]
