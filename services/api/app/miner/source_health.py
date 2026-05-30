"""Miner source health classification.

This module is intentionally route-free. It turns DB-shaped metadata rows into
small, serialisable health summaries that a future dashboard endpoint can
return without re-encoding the source-health rules.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from jeromelu_shared.db import AgentRun, Channel, ChannelMetric, Source
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .common.pipelines import (
    PIPELINE_YOUTUBE_CHANNEL_STATS,
    PIPELINE_YOUTUBE_REFRESH_VIDEOS,
    WATCHED_YOUTUBE_REFRESH_PIPELINES,
)

HEALTHY = "healthy"
WARN = "warn"
FAILED = "failed"
UNKNOWN = "unknown"

TERMINAL_FAILURE_STATUSES = frozenset({"failed", "aborted"})
COMPLETED_STATUS = "completed"

WATCHED_YOUTUBE_PIPELINES = WATCHED_YOUTUBE_REFRESH_PIPELINES


@dataclass(frozen=True)
class SourceHealthConfig:
    """Thresholds for health checks.

    The YouTube jobs are daily in prod, so a 36-hour window gives one missed
    cron slot before warning. Run failures are kept visible for two days.
    """

    channel_stats_max_age: timedelta = timedelta(hours=36)
    video_refresh_max_age: timedelta = timedelta(hours=36)
    channel_metric_max_age: timedelta = timedelta(days=8)
    failed_run_lookback: timedelta = timedelta(hours=48)
    max_samples_per_check: int = 20


@dataclass(frozen=True)
class PipelineRunInput:
    """DB-shaped subset of ``agent_runs`` used by source health."""

    run_id: str
    pipeline: str | None
    status: str
    started_at: datetime | None
    ended_at: datetime | None = None
    summary: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_agent_run(cls, run: AgentRun) -> PipelineRunInput:
        detail = run.detail_json or {}
        return cls(
            run_id=run.run_id,
            pipeline=detail.get("pipeline"),
            status=run.status,
            started_at=run.started_at,
            ended_at=run.ended_at,
            summary=run.summary,
            detail=detail,
        )


@dataclass(frozen=True)
class ChannelInput:
    """DB-shaped subset of ``channels`` used by source health."""

    channel_id: str
    name: str
    slug: str | None = None
    external_id: str | None = None
    platform: str = "youtube"
    active: bool = True


@dataclass(frozen=True)
class ChannelMetricInput:
    """Latest metric timestamp for one channel."""

    channel_id: str
    sampled_at: datetime | None
    platform: str = "youtube"


@dataclass(frozen=True)
class SourceStatusInput:
    """DB-shaped subset of ``sources`` used by source backlog health."""

    source_id: str
    ingestion_status: str
    source_type: str = "youtube"
    approved_flag: bool = True
    channel_id: str | None = None
    title: str | None = None
    transcription_status: str | None = None
    audio_s3_key: str | None = None
    extraction_method: str | None = None
    created_at: datetime | None = None
    published_at: datetime | None = None


@dataclass(frozen=True)
class HealthCheckSummary:
    """One source-health check result."""

    name: str
    status: str
    summary: str
    counts: Mapping[str, int] = field(default_factory=dict)
    samples: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "counts": dict(self.counts),
            "samples": [_serialise_mapping(sample) for sample in self.samples],
            "metadata": _serialise_mapping(self.metadata),
        }


@dataclass(frozen=True)
class SourceHealthSummary:
    """Structured Miner source-health output for API/dashboard consumers."""

    generated_at: datetime
    status: str
    checks: Sequence[HealthCheckSummary]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": _iso_or_none(self.generated_at),
            "status": self.status,
            "checks": [check.to_dict() for check in self.checks],
        }

    def check(self, name: str) -> HealthCheckSummary:
        for check in self.checks:
            if check.name == name:
                return check
        raise KeyError(name)


def build_source_health_summary(
    *,
    runs: Sequence[PipelineRunInput],
    channels: Sequence[ChannelInput],
    channel_metrics: Sequence[ChannelMetricInput],
    sources: Sequence[SourceStatusInput],
    now: datetime | None = None,
    config: SourceHealthConfig | None = None,
) -> SourceHealthSummary:
    """Classify Miner source liveness from already-loaded DB metadata."""

    config = config or SourceHealthConfig()
    generated_at = _normalise_datetime(now or datetime.now(UTC))
    normalised_runs = tuple(_normalise_run(run) for run in runs)
    active_youtube_channels = tuple(channel for channel in channels if channel.active and channel.platform == "youtube")
    youtube_sources = tuple(source for source in sources if source.approved_flag and source.source_type == "youtube")

    checks = (
        _pipeline_recency_check(
            name="channel_stats_run",
            pipeline=PIPELINE_YOUTUBE_CHANNEL_STATS,
            max_age=config.channel_stats_max_age,
            runs=normalised_runs,
            now=generated_at,
        ),
        _pipeline_recency_check(
            name="video_refresh_run",
            pipeline=PIPELINE_YOUTUBE_REFRESH_VIDEOS,
            max_age=config.video_refresh_max_age,
            runs=normalised_runs,
            now=generated_at,
        ),
        _channel_metadata_check(
            channels=active_youtube_channels,
            channel_metrics=channel_metrics,
            now=generated_at,
            config=config,
        ),
        _recent_failed_runs_check(
            runs=normalised_runs,
            now=generated_at,
            config=config,
        ),
        _source_backlog_check(
            sources=youtube_sources,
            config=config,
        ),
    )
    return SourceHealthSummary(
        generated_at=generated_at,
        status=_overall_status(checks),
        checks=checks,
    )


def build_source_health_summary_from_db(
    session: Session,
    *,
    now: datetime | None = None,
    config: SourceHealthConfig | None = None,
    run_limit: int = 200,
) -> SourceHealthSummary:
    """Load DB metadata and classify Miner source health.

    This is a thin query adapter around ``build_source_health_summary``. Unit
    tests should target the pure classifier; route code can use this helper.
    """

    return build_source_health_summary(
        runs=load_pipeline_run_inputs(session, limit=run_limit),
        channels=load_channel_inputs(session),
        channel_metrics=load_latest_channel_metric_inputs(session),
        sources=load_source_status_inputs(session),
        now=now,
        config=config,
    )


def load_pipeline_run_inputs(session: Session, *, limit: int = 200) -> tuple[PipelineRunInput, ...]:
    """Load recent Miner YouTube refresh/backfill rows per watched pipeline.

    The limit is applied per pipeline, not across all pipelines, so a burst of
    channel backfills cannot starve daily refresh/stats checks. A second pass
    loads terminal failures per pipeline so failure detection is not hidden by
    a large number of newer successful rows.
    """

    pipeline = AgentRun.detail_json["pipeline"].astext
    per_pipeline_limit = max(1, limit)
    rows_by_run_id: dict[str, AgentRun] = {}

    for pipeline_name in WATCHED_YOUTUBE_PIPELINES:
        recent_rows = session.execute(
            select(AgentRun)
            .where(AgentRun.agent_id == "miner")
            .where(pipeline == pipeline_name)
            .order_by(AgentRun.started_at.desc())
            .limit(per_pipeline_limit)
        ).scalars()
        failed_rows = session.execute(
            select(AgentRun)
            .where(AgentRun.agent_id == "miner")
            .where(pipeline == pipeline_name)
            .where(AgentRun.status.in_(TERMINAL_FAILURE_STATUSES))
            .order_by(AgentRun.started_at.desc())
            .limit(per_pipeline_limit)
        ).scalars()

        for row in tuple(recent_rows) + tuple(failed_rows):
            rows_by_run_id[str(row.run_id)] = row

    rows = sorted(rows_by_run_id.values(), key=_agent_run_observed_at, reverse=True)
    return tuple(PipelineRunInput.from_agent_run(row) for row in rows)


def load_channel_inputs(session: Session) -> tuple[ChannelInput, ...]:
    """Load active YouTube channel identity rows."""

    rows = session.execute(
        select(Channel.channel_id, Channel.slug, Channel.name, Channel.external_id, Channel.platform, Channel.active)
        .where(Channel.platform == "youtube")
        .where(Channel.active.is_(True))
        .order_by(Channel.name)
    ).all()
    return tuple(
        ChannelInput(
            channel_id=str(row.channel_id),
            slug=row.slug,
            name=row.name,
            external_id=row.external_id,
            platform=row.platform,
            active=row.active,
        )
        for row in rows
    )


def load_latest_channel_metric_inputs(session: Session) -> tuple[ChannelMetricInput, ...]:
    """Load the latest channel metric timestamp per YouTube channel."""

    rows = session.execute(
        select(
            ChannelMetric.channel_id,
            func.max(ChannelMetric.sampled_at).label("sampled_at"),
        )
        .where(ChannelMetric.platform == "youtube")
        .group_by(ChannelMetric.channel_id)
    ).all()
    return tuple(
        ChannelMetricInput(
            channel_id=str(row.channel_id),
            sampled_at=row.sampled_at,
            platform="youtube",
        )
        for row in rows
    )


def load_source_status_inputs(session: Session) -> tuple[SourceStatusInput, ...]:
    """Load approved YouTube source status fields for backlog classification."""

    rows = session.execute(
        select(
            Source.source_id,
            Source.channel_id,
            Source.title,
            Source.source_type,
            Source.approved_flag,
            Source.ingestion_status,
            Source.transcription_status,
            Source.audio_s3_key,
            Source.extraction_method,
            Source.created_at,
            Source.published_at,
        )
        .where(Source.source_type == "youtube")
        .where(Source.approved_flag.is_(True))
        .order_by(Source.published_at.desc().nullslast(), Source.created_at.desc())
    ).all()
    return tuple(
        SourceStatusInput(
            source_id=str(row.source_id),
            channel_id=str(row.channel_id) if row.channel_id else None,
            title=row.title,
            source_type=row.source_type,
            approved_flag=row.approved_flag,
            ingestion_status=row.ingestion_status,
            transcription_status=row.transcription_status,
            audio_s3_key=row.audio_s3_key,
            extraction_method=row.extraction_method,
            created_at=row.created_at,
            published_at=row.published_at,
        )
        for row in rows
    )


def _pipeline_recency_check(
    *,
    name: str,
    pipeline: str,
    max_age: timedelta,
    runs: Sequence[PipelineRunInput],
    now: datetime,
) -> HealthCheckSummary:
    matching = tuple(run for run in runs if run.pipeline == pipeline)
    completed = tuple(run for run in matching if run.status == COMPLETED_STATUS and _run_observed_at(run))
    latest = max(completed, key=lambda run: _run_observed_at(run) or datetime.min.replace(tzinfo=UTC), default=None)
    max_age_seconds = int(max_age.total_seconds())

    if latest is None:
        return HealthCheckSummary(
            name=name,
            status=UNKNOWN,
            summary=f"No completed {pipeline} run found in supplied agent_runs rows.",
            counts={"matching_runs": len(matching), "completed_runs": 0},
            metadata={"pipeline": pipeline, "max_age_seconds": max_age_seconds},
        )

    observed_at = _run_observed_at(latest)
    if observed_at is None:
        return HealthCheckSummary(
            name=name,
            status=UNKNOWN,
            summary=f"Latest completed {pipeline} run has no usable timestamp.",
            counts={"matching_runs": len(matching), "completed_runs": len(completed)},
            metadata={"pipeline": pipeline, "run_id": latest.run_id, "max_age_seconds": max_age_seconds},
        )

    age = now - observed_at
    status = HEALTHY if age <= max_age else WARN
    if status == HEALTHY:
        summary = f"Latest completed {pipeline} run is within the freshness window."
    else:
        summary = f"Latest completed {pipeline} run is older than the freshness window."

    return HealthCheckSummary(
        name=name,
        status=status,
        summary=summary,
        counts={
            "matching_runs": len(matching),
            "completed_runs": len(completed),
            "age_seconds": max(0, int(age.total_seconds())),
        },
        metadata={
            "pipeline": pipeline,
            "run_id": latest.run_id,
            "observed_at": observed_at,
            "max_age_seconds": max_age_seconds,
        },
    )


def _channel_metadata_check(
    *,
    channels: Sequence[ChannelInput],
    channel_metrics: Sequence[ChannelMetricInput],
    now: datetime,
    config: SourceHealthConfig,
) -> HealthCheckSummary:
    if not channels:
        return HealthCheckSummary(
            name="channel_metadata",
            status=UNKNOWN,
            summary="No active YouTube channel rows were supplied.",
            counts={"channels_total": 0, "channels_missing_metrics": 0, "channels_stale_metrics": 0},
            metadata={"max_metric_age_seconds": int(config.channel_metric_max_age.total_seconds())},
        )

    latest_metric_by_channel = _latest_metric_by_channel(channel_metrics)
    missing = 0
    stale = 0
    samples: list[Mapping[str, Any]] = []

    for channel in channels:
        metric = latest_metric_by_channel.get(channel.channel_id)
        if metric is None or metric.sampled_at is None:
            missing += 1
            samples.append(_channel_sample(channel, reason="missing_channel_metric", sampled_at=None))
            continue

        sampled_at = _normalise_datetime(metric.sampled_at)
        if now - sampled_at > config.channel_metric_max_age:
            stale += 1
            samples.append(_channel_sample(channel, reason="stale_channel_metric", sampled_at=sampled_at))

    if missing or stale:
        status = WARN
        summary = "Some active YouTube channels have missing or stale channel_metrics metadata."
    else:
        status = HEALTHY
        summary = "All active YouTube channels have recent channel_metrics metadata."

    return HealthCheckSummary(
        name="channel_metadata",
        status=status,
        summary=summary,
        counts={
            "channels_total": len(channels),
            "channels_missing_metrics": missing,
            "channels_stale_metrics": stale,
        },
        samples=tuple(samples[: config.max_samples_per_check]),
        metadata={"max_metric_age_seconds": int(config.channel_metric_max_age.total_seconds())},
    )


def _recent_failed_runs_check(
    *,
    runs: Sequence[PipelineRunInput],
    now: datetime,
    config: SourceHealthConfig,
) -> HealthCheckSummary:
    watched = tuple(run for run in runs if run.pipeline in WATCHED_YOUTUBE_PIPELINES)
    if not watched:
        return HealthCheckSummary(
            name="recent_failed_runs",
            status=UNKNOWN,
            summary="No watched YouTube Miner run rows were supplied.",
            counts={"watched_runs": 0, "failed_recent_runs": 0},
            metadata={
                "pipelines": WATCHED_YOUTUBE_PIPELINES,
                "lookback_seconds": int(config.failed_run_lookback.total_seconds()),
            },
        )

    cutoff = now - config.failed_run_lookback
    failed = tuple(run for run in watched if _is_recent_failed_run(run, cutoff))
    if failed:
        status = FAILED
        summary = "Recent YouTube Miner refresh/backfill failures need operator inspection."
    else:
        status = HEALTHY
        summary = "No recent failed YouTube Miner refresh/backfill runs found."

    return HealthCheckSummary(
        name="recent_failed_runs",
        status=status,
        summary=summary,
        counts={"watched_runs": len(watched), "failed_recent_runs": len(failed)},
        samples=tuple(_failed_run_sample(run) for run in failed[: config.max_samples_per_check]),
        metadata={
            "pipelines": WATCHED_YOUTUBE_PIPELINES,
            "lookback_seconds": int(config.failed_run_lookback.total_seconds()),
        },
    )


def _source_backlog_check(
    *,
    sources: Sequence[SourceStatusInput],
    config: SourceHealthConfig,
) -> HealthCheckSummary:
    if not sources:
        return HealthCheckSummary(
            name="source_backlog",
            status=UNKNOWN,
            summary="No approved YouTube source rows were supplied.",
            counts=_empty_source_backlog_counts(),
        )

    pending_audio = [source for source in sources if _is_pending_audio(source)]
    collected_missing_audio = [source for source in sources if _is_collected_missing_audio(source)]
    collected_untranscribed = [source for source in sources if _is_collected_untranscribed(source)]
    failed_audio = [source for source in sources if source.ingestion_status == "failed"]
    failed_transcription = [source for source in sources if source.transcription_status == "failed"]
    caption_risk = [source for source in sources if _has_caption_regeneration_risk(source)]

    counts = {
        "sources_total": len(sources),
        "pending_audio": len(pending_audio),
        "collected_missing_audio": len(collected_missing_audio),
        "collected_untranscribed": len(collected_untranscribed),
        "audio_fetch_failed": len(failed_audio),
        "transcription_failed": len(failed_transcription),
        "caption_regeneration_risk": len(caption_risk),
    }

    samples = _source_backlog_samples(
        groups=(
            ("pending_audio", pending_audio),
            ("collected_missing_audio", collected_missing_audio),
            ("collected_untranscribed", collected_untranscribed),
            ("audio_fetch_failed", failed_audio),
            ("transcription_failed", failed_transcription),
            ("caption_regeneration_risk", caption_risk),
        ),
        max_samples=config.max_samples_per_check,
    )

    if collected_missing_audio or failed_audio or failed_transcription:
        status = FAILED
        summary = "Some approved YouTube sources are in invalid, failed acquisition, or failed transcription states."
    elif pending_audio or collected_untranscribed or caption_risk:
        status = WARN
        summary = "Approved YouTube sources are waiting for Miner audio, Analyst transcription, or caption rework."
    else:
        status = HEALTHY
        summary = "No source backlog or failed source states found in supplied rows."

    return HealthCheckSummary(
        name="source_backlog",
        status=status,
        summary=summary,
        counts=counts,
        samples=samples,
    )


def _overall_status(checks: Sequence[HealthCheckSummary]) -> str:
    statuses = {check.status for check in checks}
    if FAILED in statuses:
        return FAILED
    if WARN in statuses:
        return WARN
    if UNKNOWN in statuses:
        return UNKNOWN
    return HEALTHY


def _normalise_run(run: PipelineRunInput) -> PipelineRunInput:
    return PipelineRunInput(
        run_id=run.run_id,
        pipeline=run.pipeline,
        status=run.status,
        started_at=_normalise_datetime(run.started_at) if run.started_at else None,
        ended_at=_normalise_datetime(run.ended_at) if run.ended_at else None,
        summary=run.summary,
        detail=run.detail,
    )


def _normalise_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _run_observed_at(run: PipelineRunInput) -> datetime | None:
    return run.ended_at or run.started_at


def _agent_run_observed_at(row: AgentRun) -> datetime:
    observed_at = getattr(row, "ended_at", None) or getattr(row, "started_at", None)
    if observed_at is None:
        return datetime.min.replace(tzinfo=UTC)
    return _normalise_datetime(observed_at)


def _is_recent_failed_run(run: PipelineRunInput, cutoff: datetime) -> bool:
    observed_at = _run_observed_at(run)
    return run.status in TERMINAL_FAILURE_STATUSES and observed_at is not None and observed_at >= cutoff


def _latest_metric_by_channel(
    metrics: Sequence[ChannelMetricInput],
) -> dict[str, ChannelMetricInput]:
    latest: dict[str, ChannelMetricInput] = {}
    for metric in metrics:
        if metric.platform != "youtube" or metric.sampled_at is None:
            latest.setdefault(metric.channel_id, metric)
            continue
        current = latest.get(metric.channel_id)
        if current is None or current.sampled_at is None:
            latest[metric.channel_id] = metric
            continue
        if _normalise_datetime(metric.sampled_at) > _normalise_datetime(current.sampled_at):
            latest[metric.channel_id] = metric
    return latest


def _is_pending_audio(source: SourceStatusInput) -> bool:
    return source.ingestion_status == "pending" and not source.audio_s3_key


def _is_collected_missing_audio(source: SourceStatusInput) -> bool:
    return source.ingestion_status == "collected" and not source.audio_s3_key


def _is_collected_untranscribed(source: SourceStatusInput) -> bool:
    return source.ingestion_status == "collected" and bool(source.audio_s3_key) and source.transcription_status is None


def _has_caption_regeneration_risk(source: SourceStatusInput) -> bool:
    return source.extraction_method == "youtube_captions" or (
        source.ingestion_status == "completed" and source.transcription_status is None
    )


def _channel_sample(channel: ChannelInput, *, reason: str, sampled_at: datetime | None) -> Mapping[str, Any]:
    return {
        "channel_id": channel.channel_id,
        "slug": channel.slug,
        "name": channel.name,
        "external_id": channel.external_id,
        "reason": reason,
        "sampled_at": sampled_at,
    }


def _failed_run_sample(run: PipelineRunInput) -> Mapping[str, Any]:
    return {
        "run_id": run.run_id,
        "pipeline": run.pipeline,
        "status": run.status,
        "started_at": run.started_at,
        "ended_at": run.ended_at,
        "summary": run.summary,
        "error": run.detail.get("error"),
        "partial_failure": run.detail.get("partial_failure"),
    }


def _source_backlog_samples(
    *,
    groups: Sequence[tuple[str, Sequence[SourceStatusInput]]],
    max_samples: int,
) -> tuple[Mapping[str, Any], ...]:
    samples: list[Mapping[str, Any]] = []
    for category, sources in groups:
        for source in sources:
            if len(samples) >= max_samples:
                return tuple(samples)
            samples.append(_source_sample(source, category=category))
    return tuple(samples)


def _source_sample(source: SourceStatusInput, *, category: str) -> Mapping[str, Any]:
    return {
        "category": category,
        "source_id": source.source_id,
        "channel_id": source.channel_id,
        "title": source.title,
        "ingestion_status": source.ingestion_status,
        "transcription_status": source.transcription_status,
        "extraction_method": source.extraction_method,
        "published_at": source.published_at,
        "created_at": source.created_at,
    }


def _empty_source_backlog_counts() -> Mapping[str, int]:
    return {
        "sources_total": 0,
        "pending_audio": 0,
        "collected_missing_audio": 0,
        "collected_untranscribed": 0,
        "audio_fetch_failed": 0,
        "transcription_failed": 0,
        "caption_regeneration_risk": 0,
    }


def _iso_or_none(value: Any) -> Any:
    if isinstance(value, datetime):
        return _normalise_datetime(value).isoformat()
    if isinstance(value, Mapping):
        return _serialise_mapping(value)
    if isinstance(value, tuple | list):
        return [_iso_or_none(item) for item in value]
    return value


def _serialise_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _iso_or_none(value) for key, value in values.items()}
