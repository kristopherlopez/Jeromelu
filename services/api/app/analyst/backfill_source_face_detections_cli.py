"""Backfill ``source_face_detections`` for existing sources.

Slice B PR 1 added the table but only the LOCAL ``visual_identify``
branch writes rows during fresh ETLs. Sources that were already
visual-ID'd before this migration have the face-track JSON cached in
S3 but no detection rows in Postgres (the JSON dropped the embeddings).

This script walks sources, picks the ones missing detections, and
re-runs visual_identify with ``force_reextract=True`` so the visual ID
pass runs end-to-end and writes both the new JSON and the detection
rows. When ``LINEUP_REMOTE=1`` (the default), the SageMaker GPU
endpoint handles the heavy lifting and round-trips embeddings via an
S3 npz artefact (~3 min per source). With ``LINEUP_REMOTE=0`` or
``force_local=True``, the local CPU path runs InsightFace at 1 fps
(~3 hours per source on a typical laptop).

Usage::

    cd services/api
    source .venv/Scripts/activate
    python -m app.analyst.backfill_source_face_detections_cli [SOURCE_ID ...]

With no args: walks every source with a face-track JSON and missing
detections. With explicit source IDs: only those (useful for targeted
backfills, idempotent if already populated).
"""

from __future__ import annotations

import argparse
import logging
import uuid
from typing import Iterable

from sqlalchemy import func as sa_func

from app.analyst.video_staging import staged_video
from app.analyst.visual_id import VisualIdError, visual_identify
from jeromelu_shared.db import (
    Source,
    SourceDocument,
    SourceFaceDetection,
    SourceSpeaker,
    SessionLocal,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
)
log = logging.getLogger("backfill-detections")


def _pyannote_turns_for_source(session, source_id: uuid.UUID) -> list[dict]:
    """Reconstruct the pyannote_turns list visual_identify expects.

    visual_identify's per-turn vote uses each turn's ``start`` /
    ``end`` / ``speaker`` only; the embeddings on SourceSpeaker aren't
    needed for the visual pass. We rebuild the list from source_speakers,
    which is faster than re-fetching the pyannote JSON from S3.
    """
    doc = session.query(SourceDocument).filter(
        SourceDocument.source_id == source_id,
    ).first()
    if not doc:
        return []
    turns = (
        session.query(SourceSpeaker)
        .filter(SourceSpeaker.document_id == doc.document_id)
        .order_by(SourceSpeaker.start_ts)
        .all()
    )
    return [
        {"start": float(t.start_ts), "end": float(t.end_ts), "speaker": t.speaker_label}
        for t in turns
    ]


def _sources_to_backfill(session, only: list[uuid.UUID] | None) -> list[Source]:
    """Sources that need backfilling.

    Criteria: has ``audio_s3_key`` (so a face-track JSON exists) and
    zero ``source_face_detections`` rows. If ``only`` is supplied, we
    intersect with that set so the operator can target specific sources.
    """
    populated_subq = (
        session.query(SourceFaceDetection.source_id)
        .distinct()
        .subquery()
    )
    q = (
        session.query(Source)
        .filter(Source.audio_s3_key.isnot(None))
        .filter(~Source.source_id.in_(populated_subq))
    )
    if only:
        q = q.filter(Source.source_id.in_(only))
    return q.order_by(Source.published_at.desc().nullslast()).all()


def backfill_one(session, source: Source) -> int:
    """Re-run visual_identify for one source and return rows written.
    Returns 0 if the source can't be processed (no video, no audio,
    etc.) and logs the reason.
    """
    if not source.audio_s3_key:
        log.warning("Skip %s (%s): no audio_s3_key", source.source_id, source.title)
        return 0
    if not source.video_s3_key and source.source_type != "youtube":
        log.warning(
            "Skip %s (%s): no video_s3_key and not YouTube — visual ID needs pixels",
            source.source_id, source.title,
        )
        return 0

    pyannote_turns = _pyannote_turns_for_source(session, source.source_id)
    if not pyannote_turns:
        log.warning(
            "Skip %s (%s): no source_speakers rows — visual ID needs turns to vote against",
            source.source_id, source.title,
        )
        return 0

    log.info(
        "Backfilling %s (%s) — %d turns, video=%s",
        source.source_id, source.title, len(pyannote_turns),
        source.video_s3_key or "(yt-dlp on demand)",
    )

    try:
        with staged_video(
            source.canonical_url,
            persistent_key=source.video_s3_key,
        ) as video_key:
            if video_key is None:
                log.warning(
                    "Skip %s: video staging returned no key", source.source_id,
                )
                return 0
            visual_identify(
                session,
                audio_s3_key=source.audio_s3_key,
                video_s3_key=video_key,
                pyannote_turns=pyannote_turns,
                source_id=source.source_id,
                # Slice B PR 1.5: remote (GPU) path now round-trips
                # embeddings via an npz artefact, so the backfill can
                # use the SageMaker endpoint instead of doing local
                # CPU InsightFace. ~3 min/source vs ~3 hr/source.
                # Set force_local=True only if LINEUP_REMOTE is off or
                # the endpoint is misbehaving.
                force_reextract=True,
            )
    except VisualIdError as exc:
        log.error("Visual ID failed for %s: %s", source.source_id, exc)
        return 0

    written = session.query(sa_func.count(SourceFaceDetection.detection_id)).filter(
        SourceFaceDetection.source_id == source.source_id,
    ).scalar() or 0
    log.info("Wrote %d detections for %s", written, source.source_id)
    return written


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source_ids", nargs="*",
        help="Optional explicit source UUIDs. If omitted, every source missing detections is processed.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    only: list[uuid.UUID] | None = None
    if args.source_ids:
        try:
            only = [uuid.UUID(s) for s in args.source_ids]
        except ValueError as exc:
            parser.error(f"invalid source_id: {exc}")
            return 2

    session = SessionLocal()
    try:
        sources = _sources_to_backfill(session, only)
        if not sources:
            log.info("Nothing to backfill — all targeted sources already have detections.")
            return 0
        log.info("Backfilling %d source(s)", len(sources))
        total = 0
        for source in sources:
            total += backfill_one(session, source)
        log.info("Done. %d detections written across %d sources.", total, len(sources))
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
