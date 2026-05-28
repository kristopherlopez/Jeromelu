"""CLI driver for Phase 4 face enrollment.

Two modes:

1. Image file:
       python -m app.analyst.enroll_face_cli <person_id> --image PATH
   Detects faces in the image, picks the largest, writes one
   PersonFaceEmbedding row.

2. Video frame:
       python -m app.analyst.enroll_face_cli <person_id> \\
           --source-id <uuid> --frame-ts <seconds>
   Decodes a single frame from the source's video at the given timestamp
   (sources.video_s3_key must be set), then enrolls as in mode 1.

`--created-by` controls the provenance tag: `manual` (default), `headshot`
(scraped reference photo), or `auto-confirmed` (Phase 5 promotion).
"""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from pathlib import Path
from uuid import UUID

from jeromelu_shared.db import Person, SessionLocal, Source

from app.analyst.video_staging import (
    VideoStagingError,
    download_persistent_video,
    extract_frame,
    staged_video_local,
)
from app.analyst.visual_id import VisualIdError, enroll_face_from_image


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enroll a Person's face from a still image or video frame.",
    )
    parser.add_argument("person_id", type=str, help="UUID of the people row")

    src = parser.add_argument_group("Source of the image")
    src.add_argument(
        "--image",
        type=str,
        help="Path to a local image file (jpg/png).",
    )
    src.add_argument(
        "--source-id",
        type=str,
        help="UUID of the sources row to extract a frame from",
    )
    src.add_argument(
        "--frame-ts",
        type=float,
        help="Frame timestamp in seconds (used with --source-id)",
    )

    parser.add_argument(
        "--created-by",
        choices=("manual", "headshot", "auto-confirmed"),
        default="manual",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )

    try:
        person_id = UUID(args.person_id)
    except ValueError:
        print(f"Invalid UUID: {args.person_id}", file=sys.stderr)
        return 2

    if args.image and (args.source_id or args.frame_ts is not None):
        print("Pick --image OR (--source-id + --frame-ts), not both.", file=sys.stderr)
        return 2
    if not args.image and not (args.source_id and args.frame_ts is not None):
        print("Need either --image PATH or (--source-id UUID --frame-ts SECONDS).", file=sys.stderr)
        return 2

    with SessionLocal() as session:
        person = session.query(Person).filter(Person.person_id == person_id).one_or_none()
        if person is None:
            print(f"No person with id {person_id}", file=sys.stderr)
            return 2
        full_name = getattr(person, "canonical_name", None) or "<unknown>"

        source_id: UUID | None = None
        frame_ts = args.frame_ts

        # Resolve image path (either user-provided or extracted from video)
        with tempfile.TemporaryDirectory(prefix="jeromelu-enroll-face-") as tmp:
            if args.image:
                image_path = Path(args.image)
                if not image_path.exists():
                    print(f"Image not found: {image_path}", file=sys.stderr)
                    return 2
            else:
                source_id = UUID(args.source_id)
                source = session.query(Source).filter(Source.source_id == source_id).one_or_none()
                if source is None:
                    print(f"No source with id {source_id}", file=sys.stderr)
                    return 2
                image_path = Path(tmp) / "frame.jpg"
                # Two video acquisition paths:
                #  1. Legacy: source row carries a persistent video_s3_key.
                #  2. Default: yt-dlp the canonical_url on demand (~10–30s
                #     for a 45-min source). New sources never persist
                #     video, so this is the steady-state path.
                try:
                    if source.video_s3_key:
                        video_path = Path(tmp) / "video.mp4"
                        download_persistent_video(source.video_s3_key, video_path)
                        extract_frame(video_path, frame_ts, image_path)
                    elif source.source_type == "youtube" and source.canonical_url:
                        with staged_video_local(source.canonical_url) as video_path:
                            extract_frame(video_path, frame_ts, image_path)
                    else:
                        print(
                            f"Source {source_id} has no video_s3_key and no YouTube "
                            "canonical_url — can't acquire a frame.",
                            file=sys.stderr,
                        )
                        return 1
                except (VisualIdError, VideoStagingError) as exc:
                    print(f"FAILED: {exc}", file=sys.stderr)
                    return 1

            print(f"Enrolling face for person {person_id}")
            print(f"  name:       {full_name}")
            if source_id:
                print(f"  source_id:  {source_id}")
                print(f"  frame_ts:   {frame_ts}s")
            else:
                print(f"  image:      {image_path}")
            print(f"  created_by: {args.created_by}")
            print()

            try:
                face_id, det_score, area = enroll_face_from_image(
                    session,
                    person_id=person_id,
                    source_id=source_id,
                    image_path=image_path,
                    frame_ts=frame_ts,
                    created_by=args.created_by,
                )
            except VisualIdError as exc:
                print(f"FAILED: {exc}", file=sys.stderr)
                return 1

    print("OK")
    print(f"  face_embedding_id:  {face_id}")
    print(f"  detection_score:    {det_score:.3f}")
    print(f"  image_area_px:      {int(area):,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
