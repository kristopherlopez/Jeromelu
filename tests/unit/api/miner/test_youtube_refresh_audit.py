"""Unit coverage for audited YouTube refresh job wrappers.

The tests patch the raw refresh jobs so no live YouTube API calls are made.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from app.miner.youtube.refresh import (
    PIPELINE_YOUTUBE_CHANNEL_STATS,
    PIPELINE_YOUTUBE_CHANNEL_VIDEOS,
    PIPELINE_YOUTUBE_REFRESH_VIDEOS,
    _source_ids_missing_initial_video_metrics,
    refresh_channel_videos,
    run_youtube_channel_stats,
    run_youtube_channel_videos,
    run_youtube_refresh_videos,
)


class _FakeRun:
    def __init__(self, run_id: str = "miner-test-run") -> None:
        self.run_id = run_id
        self.detail: dict[str, Any] = {}
        self.completed = False
        self.failed = False
        self.complete_summary: str | None = None
        self.fail_summary: str | None = None

    def complete(self, *, summary_text: str) -> None:
        self.completed = True
        self.complete_summary = summary_text

    def fail(self, exc: Exception, *, summary_text: str) -> None:
        self.failed = True
        self.fail_summary = summary_text
        self.detail["error"] = f"{type(exc).__name__}: {exc}"


def _fake_start_factory():
    runs: list[_FakeRun] = []

    def fake_start(_db, **kwargs):
        run = _FakeRun()
        run.detail.update(kwargs.get("detail") or {})
        run.detail["pipeline"] = kwargs["pipeline"]
        runs.append(run)
        return run

    return runs, fake_start


def test_daily_refresh_success_records_completed_run_detail():
    """Daily refresh wraps enumerate + stats in pipeline=youtube-refresh-videos."""
    runs, fake_start = _fake_start_factory()
    enumerate_result = {
        "channels_processed": 2,
        "total_videos_inserted": 3,
        "per_channel": [
            {"channel_id": "channel-ok", "videos_inserted": 3},
            {"channel_id": "channel-noop", "videos_inserted": 0},
        ],
    }
    stats_result = {
        "videos_total": 10,
        "videos_refreshed": 4,
        "videos_unchanged": 6,
        "sources_synced": 10,
        "batches": 1,
    }

    with (
        patch("app.miner.youtube.refresh.start_deterministic_run", side_effect=fake_start) as mock_start,
        patch("app.miner.youtube.refresh.refresh_all_channels_incremental", return_value=enumerate_result),
        patch("app.miner.youtube.refresh.refresh_all_video_stats", return_value=stats_result),
    ):
        response = run_youtube_refresh_videos(MagicMock())

    assert mock_start.call_args.kwargs["pipeline"] == PIPELINE_YOUTUBE_REFRESH_VIDEOS
    assert response == {
        "run_id": "miner-test-run",
        "ok": True,
        "enumerate": enumerate_result,
        "stats": stats_result,
    }
    assert runs[0].completed
    assert not runs[0].failed
    assert runs[0].detail["pipeline"] == PIPELINE_YOUTUBE_REFRESH_VIDEOS
    assert runs[0].detail["enumerate"]["per_channel_count"] == 2
    assert runs[0].detail["enumerate"]["channels_failed"] == 0
    assert "per_channel" not in runs[0].detail["enumerate"]
    assert runs[0].detail["stats"] == stats_result


def test_daily_refresh_partial_enumeration_marks_run_failed_without_raising():
    """HTTP-compatible partial failures still leave agent_runs.status=failed."""
    runs, fake_start = _fake_start_factory()
    enumerate_result = {
        "channels_processed": 2,
        "total_videos_inserted": 3,
        "per_channel": [
            {"channel_id": "channel-ok", "videos_inserted": 3},
            {"channel_id": "channel-failed", "external_id": "UCfail", "error": "quota exceeded"},
        ],
    }
    stats_result = {
        "videos_total": 10,
        "videos_refreshed": 4,
        "videos_unchanged": 6,
        "sources_synced": 10,
        "batches": 1,
    }

    with (
        patch("app.miner.youtube.refresh.start_deterministic_run", side_effect=fake_start) as mock_start,
        patch("app.miner.youtube.refresh.refresh_all_channels_incremental", return_value=enumerate_result),
        patch("app.miner.youtube.refresh.refresh_all_video_stats", return_value=stats_result),
    ):
        response = run_youtube_refresh_videos(MagicMock())

    assert mock_start.call_args.kwargs["pipeline"] == PIPELINE_YOUTUBE_REFRESH_VIDEOS
    assert response["ok"] is False
    assert response["enumerate"] == enumerate_result
    assert response["stats"] == stats_result
    assert response["error"] == "1 of 2 YouTube channel enumerations failed"
    assert runs[0].failed
    assert not runs[0].completed
    assert runs[0].detail["partial_failure"] is True
    assert runs[0].detail["enumerate"]["channels_failed"] == 1
    assert runs[0].detail["enumerate"]["channel_errors"] == [enumerate_result["per_channel"][1]]
    assert runs[0].detail["error"] == "RuntimeError: 1 of 2 YouTube channel enumerations failed"


def test_daily_refresh_failure_marks_run_failed_and_reraises():
    """Failures propagate to FastAPI while the audit row is marked failed."""
    runs, fake_start = _fake_start_factory()
    error = RuntimeError("youtube unavailable")

    with (
        patch("app.miner.youtube.refresh.start_deterministic_run", side_effect=fake_start) as mock_start,
        patch("app.miner.youtube.refresh.refresh_all_video_stats", side_effect=error),
    ):
        with pytest.raises(RuntimeError, match="youtube unavailable"):
            run_youtube_refresh_videos(MagicMock(), skip_enumerate=True)

    assert mock_start.call_args.kwargs["pipeline"] == PIPELINE_YOUTUBE_REFRESH_VIDEOS
    assert runs[0].failed
    assert not runs[0].completed
    assert runs[0].detail["skip_enumerate"] is True
    assert runs[0].detail["error"] == "RuntimeError: youtube unavailable"


def test_per_channel_refresh_success_records_channel_pipeline_detail():
    """Per-channel refresh exposes run_id without changing existing counts."""
    runs, fake_start = _fake_start_factory()
    channel_id = uuid4()
    channel = SimpleNamespace(
        channel_id=channel_id,
        slug="test-channel",
        name="Test Channel",
        external_id="UCtest",
    )
    refresh_result = {
        "channel_id": str(channel_id),
        "videos_listed": 5,
        "videos_inserted": 2,
        "metrics_recorded": 2,
    }

    with (
        patch("app.miner.youtube.refresh.start_deterministic_run", side_effect=fake_start) as mock_start,
        patch("app.miner.youtube.refresh.refresh_channel_videos", return_value=refresh_result) as mock_refresh,
    ):
        response = run_youtube_channel_videos(
            MagicMock(),
            channel,
            max_results=500,
            full_backfill=True,
        )

    assert mock_start.call_args.kwargs["pipeline"] == PIPELINE_YOUTUBE_CHANNEL_VIDEOS
    mock_refresh.assert_called_once()
    assert response == {"run_id": "miner-test-run", "ok": True, **refresh_result}
    assert runs[0].completed
    assert runs[0].detail["pipeline"] == PIPELINE_YOUTUBE_CHANNEL_VIDEOS
    assert runs[0].detail["channel_id"] == str(channel_id)
    assert runs[0].detail["channel_slug"] == "test-channel"
    assert runs[0].detail["full_backfill"] is True
    assert runs[0].detail["max_results"] == 500
    assert runs[0].detail["videos_inserted"] == 2


def test_per_channel_refresh_failure_marks_run_failed_and_reraises():
    """Approval-time and ad-hoc backfills keep failure rows for recovery."""
    runs, fake_start = _fake_start_factory()
    channel = SimpleNamespace(
        channel_id=uuid4(),
        slug="test-channel",
        name="Test Channel",
        external_id="UCtest",
    )

    with (
        patch("app.miner.youtube.refresh.start_deterministic_run", side_effect=fake_start) as mock_start,
        patch(
            "app.miner.youtube.refresh.refresh_channel_videos",
            side_effect=RuntimeError("playlist failed"),
        ),
    ):
        with pytest.raises(RuntimeError, match="playlist failed"):
            run_youtube_channel_videos(MagicMock(), channel, full_backfill=True)

    assert mock_start.call_args.kwargs["pipeline"] == PIPELINE_YOUTUBE_CHANNEL_VIDEOS
    assert runs[0].failed
    assert runs[0].detail["error"] == "RuntimeError: playlist failed"


def test_missing_initial_metric_lookup_includes_retry_rows_only():
    """Full-backfill retry heals existing sources that lack video_metrics."""
    channel_id = uuid4()
    source_missing_metric = uuid4()
    source_with_metric = uuid4()
    source_not_listed = uuid4()
    session = MagicMock()
    session.execute.return_value.all.return_value = [
        (source_missing_metric, "https://www.youtube.com/watch?v=abcdefghijk"),
        (source_with_metric, "https://youtu.be/lmnopqrstuv"),
        (source_not_listed, "https://youtu.be/notlisted00"),
    ]
    session.scalars.return_value.all.return_value = [source_with_metric]

    result = _source_ids_missing_initial_video_metrics(
        session,
        channel_id,
        ["abcdefghijk", "lmnopqrstuv"],
    )

    assert result == {"abcdefghijk": source_missing_metric}


def test_channel_refresh_full_backfill_records_metrics_for_existing_retry_source():
    """ON CONFLICT no-op rows still get missing first metrics on retry."""
    channel_id = uuid4()
    existing_source_id = uuid4()
    channel = SimpleNamespace(
        channel_id=channel_id,
        platform="youtube",
        external_id="UCtest",
        name="Test Channel",
    )
    videos = [
        {
            "video_id": "abcdefghijk",
            "title": "Existing Video",
            "description": "description",
            "thumbnail_url": "https://example.test/thumb.jpg",
            "url": "https://www.youtube.com/watch?v=abcdefghijk",
            "published_at": "2026-01-01T00:00:00Z",
        }
    ]
    session = MagicMock()
    session.execute.return_value.first.return_value = None

    with (
        patch("app.miner.youtube.refresh.youtube_api.list_channel_videos", return_value=videos),
        patch(
            "app.miner.youtube.refresh._source_ids_missing_initial_video_metrics",
            return_value={"abcdefghijk": existing_source_id},
        ),
        patch(
            "app.miner.youtube.refresh.youtube_api.get_video_stats",
            return_value={
                "abcdefghijk": {
                    "views": 100,
                    "likes": 5,
                    "comments": 2,
                    "duration_seconds": 123,
                }
            },
        ) as mock_stats,
    ):
        result = refresh_channel_videos(session, channel, full_backfill=True)

    assert result["videos_inserted"] == 0
    assert result["metrics_recorded"] == 1
    mock_stats.assert_called_once_with(["abcdefghijk"])
    metric = session.add.call_args.args[0]
    assert metric.source_id == existing_source_id
    assert metric.metrics == {"views": 100, "likes": 5, "comments": 2}
    session.commit.assert_called_once()
    session.rollback.assert_not_called()


def test_channel_refresh_rolls_back_source_insert_when_initial_stats_fail():
    """Stats failures cannot be committed later by run.fail on the same session."""
    channel_id = uuid4()
    new_source_id = uuid4()
    channel = SimpleNamespace(
        channel_id=channel_id,
        platform="youtube",
        external_id="UCtest",
        name="Test Channel",
    )
    videos = [
        {
            "video_id": "abcdefghijk",
            "title": "New Video",
            "description": "description",
            "thumbnail_url": "https://example.test/thumb.jpg",
            "url": "https://www.youtube.com/watch?v=abcdefghijk",
            "published_at": "2026-01-01T00:00:00Z",
        }
    ]
    session = MagicMock()
    session.execute.return_value.first.return_value = (new_source_id,)

    with (
        patch("app.miner.youtube.refresh.youtube_api.list_channel_videos", return_value=videos),
        patch(
            "app.miner.youtube.refresh._source_ids_missing_initial_video_metrics",
            return_value={"abcdefghijk": new_source_id},
        ),
        patch(
            "app.miner.youtube.refresh.youtube_api.get_video_stats",
            side_effect=RuntimeError("videos.list failed"),
        ),
    ):
        with pytest.raises(RuntimeError, match=r"videos\.list failed"):
            refresh_channel_videos(session, channel, full_backfill=True)

    session.rollback.assert_called_once()
    session.commit.assert_not_called()
    session.add.assert_not_called()


def test_channel_stats_failure_marks_run_failed_and_reraises():
    """Channel metrics refresh gets its own stable pipeline label."""
    runs, fake_start = _fake_start_factory()

    with (
        patch("app.miner.youtube.refresh.start_deterministic_run", side_effect=fake_start) as mock_start,
        patch(
            "app.miner.youtube.refresh.refresh_all_channel_stats",
            side_effect=RuntimeError("channels.list failed"),
        ),
    ):
        with pytest.raises(RuntimeError, match=r"channels\.list failed"):
            run_youtube_channel_stats(MagicMock())

    assert mock_start.call_args.kwargs["pipeline"] == PIPELINE_YOUTUBE_CHANNEL_STATS
    assert runs[0].failed
    assert runs[0].detail["pipeline"] == PIPELINE_YOUTUBE_CHANNEL_STATS
    assert runs[0].detail["error"] == "RuntimeError: channels.list failed"
