"""CLI driver for Phase 3 voice enrollment.

Usage:
    python -m app.analyst.enroll_voice_cli <person_id> <source_id> <start_ts> <end_ts>

Extracts sliding-window embeddings from the audio span and writes one
PersonVoiceprint row per valid window. Reject reasons:
- span shorter than MIN_TURN_DURATION (0.3 s)
- person_id not in `people` table
- source has no audio_s3_key
- all windows fail (silent / non-speech audio)

Recommended span: ≥10 s of clean monologue. Multiple non-contiguous
spans per Person give better registry coverage than one long run.
"""

from __future__ import annotations

import argparse
import logging
import sys
from uuid import UUID

from jeromelu_shared.db import Person, SessionLocal

from app.analyst.identify_voice import EnrollmentError, enroll


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enroll a Person's voice from a span of source audio.",
    )
    parser.add_argument("person_id", type=str, help="UUID of the people row")
    parser.add_argument("source_id", type=str, help="UUID of the sources row")
    parser.add_argument("start_ts", type=float, help="Span start (seconds)")
    parser.add_argument("end_ts", type=float, help="Span end (seconds)")
    parser.add_argument(
        "--created-by",
        choices=("manual", "auto-confirmed"),
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
        source_id = UUID(args.source_id)
    except ValueError as exc:
        print(f"Invalid UUID: {exc}", file=sys.stderr)
        return 2

    with SessionLocal() as session:
        person = session.query(Person).filter(Person.person_id == person_id).one_or_none()
        if person is None:
            print(f"No person with id {person_id}", file=sys.stderr)
            return 2
        full_name = getattr(person, "canonical_name", None) or "<unknown>"

        print(f"Enrolling voiceprint for person {person_id}")
        print(f"  name:          {full_name}")
        print(f"  source_id:     {source_id}")
        print(
            f"  span:          {args.start_ts:.2f}s - {args.end_ts:.2f}s (duration {args.end_ts - args.start_ts:.2f}s)"
        )
        print(f"  created_by:    {args.created_by}")
        print()

        try:
            result = enroll(
                session,
                person_id=person_id,
                source_id=source_id,
                start_ts=args.start_ts,
                end_ts=args.end_ts,
                created_by=args.created_by,
            )
        except EnrollmentError as exc:
            print(f"FAILED: {exc}", file=sys.stderr)
            return 1

    print("OK")
    print(f"  voiceprints_written:  {result.voiceprints_written}")
    print(f"  voiceprints_skipped:  {result.voiceprints_skipped}")
    print(f"  embedding_model:      {result.embedding_model}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
