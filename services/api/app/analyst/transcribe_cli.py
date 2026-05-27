"""CLI driver for Analyst's transcript materialisation.

Usage:
    python -m app.analyst.transcribe_cli <source_id>
    python -m app.analyst.transcribe_cli <source_id> --force

Refuses to run if Scout hasn't already collected the audio (audio_s3_key
must be set). Use `python -m app.scout.media.audio_cli <source_id>` first.
"""

from __future__ import annotations

import argparse
import logging
import sys
from uuid import UUID

from sqlalchemy.orm import joinedload

from jeromelu_shared.db import SessionLocal, Source

from app.analyst.transcribe import (
    MissingAudioError,
    TranscriptionError,
    transcribe,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialise a Deepgram transcript for a single Source.",
    )
    parser.add_argument("source_id", type=str, help="UUID of the sources row")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace any existing SourceDocument for this source.",
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
        source_id = UUID(args.source_id)
    except ValueError:
        print(f"Invalid UUID: {args.source_id}", file=sys.stderr)
        return 2

    with SessionLocal() as session:
        source = (
            session.query(Source)
            .options(joinedload(Source.documents))
            .filter(Source.source_id == source_id)
            .one_or_none()
        )
        if source is None:
            print(f"No source with id {source_id}", file=sys.stderr)
            return 2

        print(f"Transcribing source {source.source_id}")
        print(f"  title:        {source.title}")
        print(f"  audio_s3_key: {source.audio_s3_key}")
        print()

        try:
            result = transcribe(session, source, force=args.force)
        except MissingAudioError as exc:
            print(f"FAILED (no audio): {exc}", file=sys.stderr)
            print("Hint: run `make collect-audio SOURCE_ID=...` first.", file=sys.stderr)
            return 1
        except TranscriptionError as exc:
            print(f"FAILED: {exc}", file=sys.stderr)
            return 1

    print("OK")
    print(f"  document_id:        {result.document_id}")
    print(f"  transcript_s3_key:  {result.transcript_s3_key}")
    print(f"  pyannote_s3_key:    {result.pyannote_s3_key}")
    print(f"  duration_seconds:   {result.duration_seconds}")
    print(f"  speakers_recorded:  {result.speakers_recorded}")
    print(f"  turns_recorded:     {result.turns_recorded}")
    print(f"  turns_identified:   {result.turns_identified}")
    print(f"    voice_match:      {result.turns_voice_match}")
    print(f"    visual_match:     {result.turns_visual_match}")
    print(f"    voice+face:       {result.turns_fusion_voice_face}")
    print(f"    disagreements:    {result.turns_fusion_disagreement}")
    print(f"  video_format:       {result.video_format}")
    print(f"  face_track_s3_key:  {result.face_track_s3_key}")
    print(f"  chunks_recorded:    {result.chunks_recorded}")
    print(f"  chunks_unassigned:  {result.chunks_unassigned}")
    print(f"  deepgram_model:     {result.deepgram_model}")
    print(f"  pyannote_model:     {result.pyannote_model}")
    print(f"  embedding_model:    {result.embedding_model}")
    print(f"  deepgram_request:   {result.deepgram_request_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
