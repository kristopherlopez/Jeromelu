"""Bounded drain helpers for Scout media and Analyst hand-off queues."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from uuid import UUID

from jeromelu_shared.db import Source
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DrainFailure:
    source_id: str
    error: str


@dataclass(frozen=True)
class DrainResult:
    selected: int
    succeeded: int
    failed: int
    failures: tuple[DrainFailure, ...]


def require_positive_limit(limit: int) -> int:
    """Validate a drain bound and return it for CLI/parser use."""
    if limit < 1:
        raise ValueError("limit must be >= 1")
    return limit


def select_pending_audio_source_ids(session: Session, *, limit: int) -> list[UUID]:
    """Select approved YouTube sources still waiting for Scout audio."""
    limit = require_positive_limit(limit)
    rows = (
        session.query(Source.source_id)
        .filter(
            Source.approved_flag.is_(True),
            Source.source_type == "youtube",
            Source.ingestion_status == "pending",
            Source.audio_s3_key.is_(None),
        )
        .order_by(Source.published_at.desc(), Source.created_at.desc(), Source.source_id)
        .limit(limit)
        .all()
    )
    return [row[0] for row in rows]


def select_collected_untranscribed_source_ids(session: Session, *, limit: int) -> list[UUID]:
    """Select collected sources that have no transcript materialised yet."""
    limit = require_positive_limit(limit)
    rows = (
        session.query(Source.source_id)
        .filter(
            Source.approved_flag.is_(True),
            Source.ingestion_status == "collected",
            Source.audio_s3_key.is_not(None),
            Source.transcription_status.is_(None),
            ~Source.documents.any(),
        )
        .order_by(Source.published_at.desc(), Source.created_at.desc(), Source.source_id)
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
) -> DrainResult:
    """Run a per-source processor with one DB session per source.

    The single-source processors own their own commits. This wrapper catches
    each failure, rolls back that source's session, and keeps draining the
    remaining selected rows.
    """
    succeeded = 0
    failures: list[DrainFailure] = []

    for source_id in source_ids:
        with session_factory() as session:
            try:
                query = session.query(Source)
                for option in load_options:
                    query = query.options(option)
                source = query.filter(Source.source_id == source_id).one_or_none()
                if source is None:
                    raise RuntimeError("source no longer exists")

                process_source(session, source)
                succeeded += 1
            except Exception as exc:
                session.rollback()
                logger.exception("Drain failed for source %s", source_id)
                failures.append(DrainFailure(source_id=str(source_id), error=str(exc)))

    return DrainResult(
        selected=len(source_ids),
        succeeded=succeeded,
        failed=len(failures),
        failures=tuple(failures),
    )
