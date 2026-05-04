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
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import UUID

from jeromelu_shared.config import settings
from jeromelu_shared.db import Person, SessionLocal, Source
from jeromelu_shared.s3 import get_s3_client

from app.analyst.visual_id import VisualIdError, enroll_face_from_image


def _extract_video_frame(video_s3_key: str, ts: float, dest: Path) -> None:
    """Download the video and use ffmpeg to dump one frame at `ts` to dest."""
    if shutil.which("ffmpeg") is None:
        raise VisualIdError("ffmpeg not found on PATH")

    with tempfile.TemporaryDirectory(prefix="jeromelu-frame-") as tmp:
        tmpdir = Path(tmp)
        video_path = tmpdir / "video.mp4"
        client = get_s3_client()
        client.download_file(settings.s3_audio_bucket, video_s3_key, str(video_path))
        proc = subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", f"{ts:.3f}",
                "-i", str(video_path),
                "-frames:v", "1",
                "-q:v", "2",
                str(dest),
            ],
            capture_output=True,
        )
        if proc.returncode != 0:
            raise VisualIdError(
                f"ffmpeg frame extraction failed at ts={ts}: "
                f"{proc.stderr.decode('utf-8', errors='replace')[:500]}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enroll a Person's face from a still image or video frame.",
    )
    parser.add_argument("person_id", type=str, help="UUID of the people row")

    src = parser.add_argument_group("Source of the image")
    src.add_argument(
        "--image", type=str,
        help="Path to a local image file (jpg/png).",
    )
    src.add_argument(
        "--source-id", type=str,
        help="UUID of the sources row to extract a frame from",
    )
    src.add_argument(
        "--frame-ts", type=float,
        help="Frame timestamp in seconds (used with --source-id)",
    )

    parser.add_argument(
        "--created-by",
        choices=("manual", "headshot", "auto-confirmed"),
        default="manual",
    )
    parser.add_argument(
        "--log-level", default="INFO",
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
                if not source.video_s3_key:
                    print(
                        f"Source {source_id} has no video_s3_key — run "
                        "`make collect-video SOURCE_ID=...` first.",
                        file=sys.stderr,
                    )
                    return 1
                image_path = Path(tmp) / "frame.jpg"
                try:
                    _extract_video_frame(source.video_s3_key, frame_ts, image_path)
                except VisualIdError as exc:
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
