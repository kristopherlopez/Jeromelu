"""Bounded drain helpers for Scout media and Analyst hand-off queues."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from uuid import UUID

from jeromelu_shared.db import Source
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


SourceCriteria = Sequence[object]


@dataclass(frozen=True)
class DrainFailure:
    source_id: str
    error: str


@dataclass(frozen=True)
class DrainResult:
    selected: int
    succeeded: int
    skipped: int
    failed: int
    failures: tuple[DrainFailure, ...]


def require_positive_limit(limit: int) -> int:
    """Validate a drain bound and return it for CLI/parser use."""
    if limit < 1:
        raise ValueError("limit must be >= 1")
    return limit


def pending_audio_source_criteria() -> tuple[object, ...]:
    """Eligibility criteria for Scout audio acquisition."""
    return (
        Source.approved_flag.is_(True),
        Source.source_type == "youtube",
        Source.ingestion_status == "pending",
        Source.audio_s3_key.is_(None),
    )


def collected_untranscribed_source_criteria() -> tuple[object, ...]:
    """Eligibility criteria for Analyst transcription hand-off."""
    return (
        Source.approved_flag.is_(True),
        Source.ingestion_status == "collected",
        Source.audio_s3_key.is_not(None),
        Source.transcription_status.is_(None),
        ~Source.documents.any(),
    )


def _with_drain_lock(query):
    """Lock claimed source rows on databases that support row locks."""
    return query.with_for_update(skip_locked=True, of=Source)


def select_pending_audio_source_ids(session: Session, *, limit: int) -> list[UUID]:
    """Select approved YouTube sources still waiting for Scout audio."""
    limit = require_positive_limit(limit)
    rows = (
        session.query(Source.source_id)
        .filter(*pending_audio_source_criteria())
        .order_by(Source.published_at.desc(), Source.created_at.desc(), Source.source_id)
        .with_for_update(skip_locked=True, of=Source)
        .limit(limit)
        .all()
    )
    return [row[0] for row in rows]


def select_collected_untranscribed_source_ids(session: Session, *, limit: int) -> list[UUID]:
    """Select collected sources that have no transcript materialised yet."""
    limit = require_positive_limit(limit)
    rows = (
        session.query(Source.source_id)
        .filter(*collected_untranscribed_source_criteria())
        .order_by(Source.published_at.desc(), Source.created_at.desc(), Source.source_id)
        .with_for_update(skip_locked=True, of=Source)
        .limit(limit)
        .all()
    )
    return [row[0] for row in rows]


def drain_source_ids(
    *,
    session_factory: Callable[[], Session],
    source_ids: Sequence[UUID],
    process_source: Callable[[Session, Source], object],
    load_options: Sequence[object] = (),
    eligibility_criteria: SourceCriteria = (),
) -> DrainResult:
    """Run a per-source processor with one DB session per source.

    The single-source processors own their own commits. This wrapper catches
    each failure, rolls back that source's session, and keeps draining the
    remaining selected rows. Each source is locked and eligibility-filtered
    again in the processing session so overlapping drain runs do not duplicate
    work after stale selection.
    """
    succeeded = 0
    skipped = 0
    failures: list[DrainFailure] = []

    for source_id in source_ids:
        with session_factory() as session:
            try:
                query = session.query(Source)
                for option in load_options:
                    query = query.options(option)
                source = (
                    _with_drain_lock(query)
                    .filter(Source.source_id == source_id, *eligibility_criteria)
                    .one_or_none()
                )
                if source is None:
                    skipped += 1
                    logger.info("Drain skipped source %s; no longer eligible or currently locked", source_id)
                    continue

                process_source(session, source)
                succeeded += 1
            except Exception as exc:
                session.rollback()
                logger.exception("Drain failed for source %s", source_id)
                failures.append(DrainFailure(source_id=str(source_id), error=str(exc)))

    return DrainResult(
        selected=len(source_ids),
        succeeded=succeeded,
        skipped=skipped,
        failed=len(failures),
        failures=tuple(failures),
    )
