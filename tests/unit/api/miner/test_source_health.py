from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.miner.common.pipelines import (
    PIPELINE_YOUTUBE_CHANNEL_STATS,
    PIPELINE_YOUTUBE_CHANNEL_VIDEOS,
    PIPELINE_YOUTUBE_REFRESH_VIDEOS,
)
from app.miner.source_health import (
    FAILED,
    HEALTHY,
    UNKNOWN,
    WARN,
    ChannelInput,
    ChannelMetricInput,
    PipelineRunInput,
    SourceHealthConfig,
    SourceStatusInput,
    build_source_health_summary,
)

NOW = datetime(2026, 5, 30, 0, 0, tzinfo=UTC)


def _run(
    pipeline: str,
    status: str = "completed",
    *,
    hours_ago: int = 1,
    run_id: str | None = None,
    detail: dict | None = None,
) -> PipelineRunInput:
    return PipelineRunInput(
        run_id=run_id or f"{pipeline}-{status}",
        pipeline=pipeline,
        status=status,
        started_at=NOW - timedelta(hours=hours_ago, minutes=10),
        ended_at=NOW - timedelta(hours=hours_ago),
        summary=f"{pipeline} {status}",
        detail=detail or {"pipeline": pipeline},
    )


def test_healthy_source_health_summary_uses_recent_runs_metrics_and_empty_backlog():
    summary = build_source_health_summary(
        runs=[
            _run(PIPELINE_YOUTUBE_CHANNEL_STATS),
            _run(PIPELINE_YOUTUBE_REFRESH_VIDEOS),
        ],
        channels=[
            ChannelInput(channel_id="channel-1", slug="one", name="One", external_id="UC1"),
            ChannelInput(channel_id="channel-2", slug="two", name="Two", external_id="UC2"),
        ],
        channel_metrics=[
            ChannelMetricInput(channel_id="channel-1", sampled_at=NOW - timedelta(days=1)),
            ChannelMetricInput(channel_id="channel-2", sampled_at=NOW - timedelta(days=2)),
        ],
        sources=[
            SourceStatusInput(
                source_id="source-1",
                ingestion_status="collected",
                transcription_status="transcribed",
                audio_s3_key="youtube/channel/video.m4a",
                extraction_method="deepgram_v1",
            )
        ],
        now=NOW,
    )

    assert summary.status == HEALTHY
    assert summary.check("channel_stats_run").status == HEALTHY
    assert summary.check("video_refresh_run").status == HEALTHY
    assert summary.check("channel_metadata").counts == {
        "channels_total": 2,
        "channels_missing_metrics": 0,
        "channels_stale_metrics": 0,
    }
    assert summary.check("source_backlog").counts["sources_total"] == 1
    assert summary.to_dict()["generated_at"] == "2026-05-30T00:00:00+00:00"


def test_missing_run_and_metric_data_is_not_classified_as_healthy():
    summary = build_source_health_summary(
        runs=[],
        channels=[ChannelInput(channel_id="channel-1", slug="one", name="One", external_id="UC1")],
        channel_metrics=[],
        sources=[],
        now=NOW,
    )

    assert summary.status == WARN
    assert summary.check("channel_stats_run").status == UNKNOWN
    assert summary.check("video_refresh_run").status == UNKNOWN
    assert summary.check("channel_metadata").status == WARN
    assert summary.check("channel_metadata").counts["channels_missing_metrics"] == 1
    assert summary.check("recent_failed_runs").status == UNKNOWN
    assert summary.check("source_backlog").status == UNKNOWN


def test_stale_channel_and_video_refresh_runs_warn():
    summary = build_source_health_summary(
        runs=[
            _run(PIPELINE_YOUTUBE_CHANNEL_STATS, hours_ago=40),
            _run(PIPELINE_YOUTUBE_REFRESH_VIDEOS, hours_ago=48),
        ],
        channels=[ChannelInput(channel_id="channel-1", slug="one", name="One", external_id="UC1")],
        channel_metrics=[ChannelMetricInput(channel_id="channel-1", sampled_at=NOW - timedelta(days=1))],
        sources=[
            SourceStatusInput(
                source_id="source-1",
                ingestion_status="collected",
                transcription_status="transcribed",
                audio_s3_key="youtube/channel/video.m4a",
            )
        ],
        now=NOW,
    )

    assert summary.status == WARN
    assert summary.check("channel_stats_run").status == WARN
    assert summary.check("channel_stats_run").counts["age_seconds"] == 40 * 60 * 60
    assert summary.check("video_refresh_run").status == WARN
    assert summary.check("video_refresh_run").counts["age_seconds"] == 48 * 60 * 60


def test_recent_failed_refresh_or_backfill_run_marks_summary_failed():
    summary = build_source_health_summary(
        runs=[
            _run(PIPELINE_YOUTUBE_CHANNEL_STATS),
            _run(PIPELINE_YOUTUBE_REFRESH_VIDEOS),
            _run(
                PIPELINE_YOUTUBE_CHANNEL_VIDEOS,
                "failed",
                hours_ago=2,
                run_id="failed-backfill",
                detail={
                    "pipeline": PIPELINE_YOUTUBE_CHANNEL_VIDEOS,
                    "error": "RuntimeError: playlist failed",
                },
            ),
        ],
        channels=[ChannelInput(channel_id="channel-1", slug="one", name="One", external_id="UC1")],
        channel_metrics=[ChannelMetricInput(channel_id="channel-1", sampled_at=NOW - timedelta(days=1))],
        sources=[
            SourceStatusInput(
                source_id="source-1",
                ingestion_status="collected",
                transcription_status="transcribed",
                audio_s3_key="youtube/channel/video.m4a",
            )
        ],
        now=NOW,
    )

    failed_runs = summary.check("recent_failed_runs")
    assert summary.status == FAILED
    assert failed_runs.status == FAILED
    assert failed_runs.counts["failed_recent_runs"] == 1
    assert failed_runs.samples[0]["run_id"] == "failed-backfill"
    assert failed_runs.samples[0]["error"] == "RuntimeError: playlist failed"


def test_source_backlog_counts_pending_failures_and_caption_regeneration_risk():
    summary = build_source_health_summary(
        runs=[
            _run(PIPELINE_YOUTUBE_CHANNEL_STATS),
            _run(PIPELINE_YOUTUBE_REFRESH_VIDEOS),
        ],
        channels=[ChannelInput(channel_id="channel-1", slug="one", name="One", external_id="UC1")],
        channel_metrics=[ChannelMetricInput(channel_id="channel-1", sampled_at=NOW - timedelta(days=1))],
        sources=[
            SourceStatusInput(source_id="pending", ingestion_status="pending"),
            SourceStatusInput(source_id="collected-missing-audio", ingestion_status="collected"),
            SourceStatusInput(
                source_id="collected",
                ingestion_status="collected",
                audio_s3_key="youtube/channel/video.m4a",
            ),
            SourceStatusInput(source_id="unreachable", ingestion_status="failed"),
            SourceStatusInput(
                source_id="transcript-failed",
                ingestion_status="collected",
                transcription_status="failed",
                audio_s3_key="youtube/channel/video.m4a",
            ),
            SourceStatusInput(
                source_id="legacy-captions",
                ingestion_status="completed",
                extraction_method="youtube_captions",
            ),
            SourceStatusInput(
                source_id="done",
                ingestion_status="collected",
                transcription_status="transcribed",
                audio_s3_key="youtube/channel/video.m4a",
                extraction_method="deepgram_v1",
            ),
        ],
        now=NOW,
    )

    backlog = summary.check("source_backlog")
    assert summary.status == FAILED
    assert backlog.status == FAILED
    assert backlog.counts == {
        "sources_total": 7,
        "pending_audio": 1,
        "collected_missing_audio": 1,
        "collected_untranscribed": 1,
        "audio_fetch_failed": 1,
        "transcription_failed": 1,
        "caption_regeneration_risk": 1,
    }
    assert {sample["category"] for sample in backlog.samples} == {
        "pending_audio",
        "collected_missing_audio",
        "collected_untranscribed",
        "audio_fetch_failed",
        "transcription_failed",
        "caption_regeneration_risk",
    }


def test_channel_metadata_warns_for_stale_or_missing_per_channel_metrics():
    summary = build_source_health_summary(
        runs=[
            _run(PIPELINE_YOUTUBE_CHANNEL_STATS),
            _run(PIPELINE_YOUTUBE_REFRESH_VIDEOS),
        ],
        channels=[
            ChannelInput(channel_id="fresh", slug="fresh", name="Fresh", external_id="UCfresh"),
            ChannelInput(channel_id="stale", slug="stale", name="Stale", external_id="UCstale"),
            ChannelInput(channel_id="missing", slug="missing", name="Missing", external_id="UCmissing"),
        ],
        channel_metrics=[
            ChannelMetricInput(channel_id="fresh", sampled_at=NOW - timedelta(days=1)),
            ChannelMetricInput(channel_id="stale", sampled_at=NOW - timedelta(days=10)),
        ],
        sources=[
            SourceStatusInput(
                source_id="source-1",
                ingestion_status="collected",
                transcription_status="transcribed",
                audio_s3_key="youtube/channel/video.m4a",
            )
        ],
        now=NOW,
        config=SourceHealthConfig(channel_metric_max_age=timedelta(days=7)),
    )

    channel_metadata = summary.check("channel_metadata")
    assert summary.status == WARN
    assert channel_metadata.status == WARN
    assert channel_metadata.counts["channels_missing_metrics"] == 1
    assert channel_metadata.counts["channels_stale_metrics"] == 1
    assert [sample["reason"] for sample in channel_metadata.samples] == [
        "stale_channel_metric",
        "missing_channel_metric",
    ]
