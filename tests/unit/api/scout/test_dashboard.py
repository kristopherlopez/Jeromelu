"""Unit coverage for the Scout pipeline dashboard read model."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from app.scout.dashboard import build_scout_dashboard, scout_dashboard
from jeromelu_shared.db import AgentRun


def _run(
    run_id: str,
    *,
    status: str,
    started_at: datetime,
    detail_json: dict[str, Any] | None,
    ended_at: datetime | None = None,
    summary: str = "",
    total_cost_usd: Decimal | None = None,
):
    return SimpleNamespace(
        run_id=run_id,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
        summary=summary,
        detail_json=detail_json,
        total_cost_usd=total_cost_usd,
    )


def test_build_dashboard_groups_recent_rows_by_pipeline_and_preserves_latest_run():
    now = datetime(2026, 5, 30, 1, 2, 3, tzinfo=UTC)
    rows = [
        _run(
            "latest-refresh",
            status="completed",
            started_at=now,
            ended_at=now + timedelta(seconds=20),
            summary="Daily YouTube refresh complete",
            total_cost_usd=Decimal("0.010000"),
            detail_json={
                "pipeline": "youtube-refresh-videos",
                "enumerate": {
                    "channels_processed": 2,
                    "per_channel": [{"channel_id": "a"}, {"channel_id": "b"}],
                },
                "stats": {"videos_total": 10, "videos_refreshed": 4},
            },
        ),
        _run(
            "channel-run",
            status="running",
            started_at=now - timedelta(minutes=10),
            total_cost_usd=None,
            detail_json={
                "pipeline": "youtube-channel-videos",
                "channel_slug": "nrl-test",
                "max_results": 500,
            },
        ),
        _run(
            "older-refresh",
            status="failed",
            started_at=now - timedelta(hours=1),
            summary="1 channel failed",
            total_cost_usd=Decimal("0.005000"),
            detail_json={
                "pipeline": "youtube-refresh-videos",
                "partial_failure": True,
                "channel_errors": [{"channel_id": "failed"}],
            },
        ),
    ]

    response = build_scout_dashboard(rows, limit=500)

    assert response["window"] == {"limit": 500, "row_count": 3, "pipeline_count": 2}
    assert response["pipeline_order"] == ["youtube-refresh-videos", "youtube-channel-videos"]

    refresh = response["pipelines"]["youtube-refresh-videos"]
    assert refresh["last_run_id"] == "latest-refresh"
    assert refresh["status"] == "completed"
    assert refresh["started_at"] == now.isoformat()
    assert refresh["ended_at"] == (now + timedelta(seconds=20)).isoformat()
    assert refresh["summary"] == "Daily YouTube refresh complete"
    assert refresh["total_cost_usd"] == 0.01
    assert refresh["recent_total_cost_usd"] == 0.015
    assert refresh["run_count"] == 2
    assert refresh["status_counts"] == {"completed": 1, "failed": 1}
    assert refresh["recent_failure_count"] == 1
    assert refresh["detail"]["enumerate"] == {
        "channels_processed": 2,
        "per_channel_count": 2,
    }
    assert "pipeline" not in refresh["detail"]

    channel = response["pipelines"]["youtube-channel-videos"]
    assert channel["last_run_id"] == "channel-run"
    assert channel["status"] == "running"
    assert channel["detail"] == {"channel_slug": "nrl-test", "max_results": 500}


def test_build_dashboard_handles_null_or_missing_pipeline_detail():
    now = datetime(2026, 5, 30, tzinfo=UTC)
    rows = [
        _run("missing-detail", status="aborted", started_at=now, detail_json=None),
        _run("empty-detail", status="completed", started_at=now - timedelta(minutes=1), detail_json={}),
    ]

    response = build_scout_dashboard(rows, limit=50)

    unclassified = response["pipelines"]["unclassified"]
    assert response["pipeline_order"] == ["unclassified"]
    assert unclassified["last_run_id"] == "missing-detail"
    assert unclassified["status"] == "aborted"
    assert unclassified["detail"] == {}
    assert unclassified["run_count"] == 2
    assert unclassified["status_counts"] == {"aborted": 1, "completed": 1}
    assert unclassified["recent_failure_count"] == 1


def test_build_dashboard_caps_broad_detail_objects():
    now = datetime(2026, 5, 30, tzinfo=UTC)
    detail_json = {"pipeline": "wide-detail"} | {f"k{i}": i for i in range(40)}
    rows = [
        _run(
            "wide-run",
            status="completed",
            started_at=now,
            detail_json=detail_json,
        )
    ]

    response = build_scout_dashboard(rows, limit=50)

    detail = response["pipelines"]["wide-detail"]["detail"]
    assert len(detail) == 30
    assert detail["detail_keys_truncated"] == 11
    assert "k29" not in detail


def test_dashboard_endpoint_queries_recent_scout_runs():
    now = datetime(2026, 5, 30, tzinfo=UTC)
    rows = [
        _run(
            "run-1",
            status="completed",
            started_at=now,
            detail_json={"pipeline": "youtube-discovery"},
        )
    ]
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.limit.return_value = query
    query.all.return_value = rows
    db = MagicMock()
    db.query.return_value = query

    response = scout_dashboard(limit=25, db=db)

    db.query.assert_called_once_with(AgentRun)
    filter_arg = query.filter.call_args.args[0]
    assert str(filter_arg.compile(compile_kwargs={"literal_binds": True})) == "agent_runs.agent_id = 'scout'"
    order_arg = query.order_by.call_args.args[0]
    assert str(order_arg.compile(compile_kwargs={"literal_binds": True})) == "agent_runs.started_at DESC"
    query.limit.assert_called_once_with(25)
    assert response["window"] == {"limit": 25, "row_count": 1, "pipeline_count": 1}
    assert response["pipelines"]["youtube-discovery"]["last_run_id"] == "run-1"
