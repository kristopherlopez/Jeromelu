"""Regenerate cached face-track JSON in S3 from ``source_face_detections``.

Companion to ``POST /api/sources/{source_id}/face-track/regenerate``,
intended for batch / retroactive use:

  - Fixes sources whose bulk-assign happened *before* the inline-regen
    hook was added (commit ade028a). Symptom: the YouTube overlay shows
    "?" for a face the DB knows is attributed.
  - Re-runs after any path that mutates ``matched_person_id`` /
    ``attributed_person_id`` outside the bulk-assign endpoint.

Usage::

    cd services/api
    source .venv/Scripts/activate

    # Regenerate one or more specific sources:
    python -m app.analyst.regen_face_track_cli <source-uuid> [<source-uuid> ...]

    # Walk every source with a face-track and regenerate (idempotent
    # but rewrites every JSON — slow on large catalogues):
    python -m app.analyst.regen_face_track_cli --all

    # Only regenerate sources whose cached JSON has fewer distinct
    # person_ids than the DB — i.e. the JSON is demonstrably stale.
    # Fast pre-filter; the right default for a bulk fix-up:
    python -m app.analyst.regen_face_track_cli --all --stale-only

Safe to interrupt: each source is its own commit. Re-running picks
up where it left off.
"""

from __future__ import annotations

import argparse
import json
import logging
import uuid
from typing import Iterable

from jeromelu_shared.db import (
    SessionLocal,
    Source,
    SourceFaceDetection,
)
from jeromelu_shared.s3 import download_raw

from app.analyst.visual_id import (
    _face_track_s3_key_from_audio,
    regenerate_face_track_json_from_detections,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
)
log = logging.getLogger("regen-face-track")


def _candidate_sources(
    session, only: list[uuid.UUID] | None,
) -> list[Source]:
    """Sources that have an audio key (so a face-track JSON could exist)."""
    q = session.query(Source).filter(Source.audio_s3_key.isnot(None))
    if only:
        q = q.filter(Source.source_id.in_(only))
    return q.order_by(Source.published_at.desc().nullslast()).all()


def _json_distinct_person_ids(audio_s3_key: str) -> set[str] | None:
    """Read the cached JSON and return its distinct non-null person_ids.

    Returns None if the JSON is missing or unparseable — callers treat
    that as "no info, regenerate anyway" rather than skipping silently.
    """
    key = _face_track_s3_key_from_audio(audio_s3_key)
    try:
        doc = json.loads(download_raw(key))
    except Exception:
        return None
    pids: set[str] = set()
    for frame in doc.get("frames", []):
        for face in frame.get("faces", []):
            pid = face.get("person_id")
            if pid:
                pids.add(pid)
    return pids


def _db_distinct_person_ids(session, source_id: uuid.UUID) -> set[str]:
    rows = (
        session.query(SourceFaceDetection.matched_person_id)
        .filter(
            SourceFaceDetection.source_id == source_id,
            SourceFaceDetection.matched_person_id.isnot(None),
        )
        .distinct()
        .all()
    )
    return {str(r[0]) for r in rows}


def _is_stale(session, source: Source) -> bool:
    """A source is stale when the DB has at least one matched person_id
    the cached JSON doesn't carry. The reverse direction (JSON has a
    person the DB doesn't) is also possible but rarer — we treat it as
    stale too so a regen overwrites the JSON with the canonical DB view.
    """
    db_pids = _db_distinct_person_ids(session, source.source_id)
    json_pids = _json_distinct_person_ids(source.audio_s3_key)
    if json_pids is None:
        # No readable JSON — nothing to regenerate from (the helper
        # bails for the same reason). Skip rather than spam errors.
        return False
    return db_pids != json_pids


def regen_one(session, source: Source) -> bool:
    """Regenerate one source. Returns True on success, False on failure.
    Failures are logged but don't abort the batch.
    """
    try:
        key = regenerate_face_track_json_from_detections(session, source.source_id)
    except Exception as exc:
        log.error("Regen failed for %s: %s", source.source_id, exc)
        return False
    if not key:
        log.warning(
            "Skip %s: no cached JSON or no detections to base regen on",
            source.source_id,
        )
        return False
    log.info("Regenerated %s (%s)", source.source_id, source.title)
    return True


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "source_ids", nargs="*", default=[],
        help="Explicit source UUIDs to regenerate.",
    )
    group.add_argument(
        "--all", action="store_true",
        help="Walk every source with audio_s3_key set.",
    )
    parser.add_argument(
        "--stale-only", action="store_true",
        help=(
            "Only regenerate sources whose cached JSON's distinct "
            "person_ids differ from the DB's. Recommended with --all."
        ),
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
        sources = _candidate_sources(session, only)
        if not sources:
            log.info("No matching sources found.")
            return 0

        if args.stale_only:
            before = len(sources)
            sources = [s for s in sources if _is_stale(session, s)]
            log.info(
                "Stale filter: %d / %d sources need regen", len(sources), before,
            )
            if not sources:
                return 0

        log.info("Regenerating face-track JSON for %d source(s)", len(sources))
        ok = 0
        failed = 0
        for source in sources:
            if regen_one(session, source):
                ok += 1
            else:
                failed += 1
        log.info("Done. %d ok, %d failed.", ok, failed)
        return 0 if failed == 0 else 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
