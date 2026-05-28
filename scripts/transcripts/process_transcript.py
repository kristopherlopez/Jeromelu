"""Process YouTube transcript JSON files — prepare (stitch+chunk) and write (persist to DB).

Usage:
    python scripts/process_transcript.py prepare <path>
    python scripts/process_transcript.py write <path> --claims '<json>' [--claims-file <file>]
    python scripts/process_transcript.py update-transcript <path>
    python scripts/process_transcript.py reset
"""

import argparse
import io
import json
import sys
from pathlib import Path

# Force UTF-8 stdout on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Add repo root to path so we can import packages
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "shared"))

from jeromelu_shared.db import Claim, ClaimChunk, SessionLocal, Source, SourceChunk, SourceDocument
from scripts.extraction.chunker import chunk_segments
from scripts.extraction.stitcher import stitch_segments
from scripts.extraction.writer import source_exists, write_transcript


def _find_raw_path(clean_path: Path) -> Path | None:
    """Given a clean transcript path, find the matching raw transcript."""
    raw_path = Path(str(clean_path).replace("/clean/", "/raw/").replace("\\clean\\", "\\raw\\"))
    return raw_path if raw_path.exists() and raw_path != clean_path else None


def cmd_prepare(args: argparse.Namespace) -> None:
    """Load transcript JSON, stitch segments, chunk text, print JSON to stdout."""
    path = Path(args.path)
    if not path.exists():
        print(json.dumps({"error": f"File not found: {path}"}))
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    video_id = data["video_id"]
    canonical_url = f"https://youtube.com/watch?v={video_id}"

    # Idempotency check
    if source_exists(canonical_url):
        print(
            json.dumps(
                {
                    "already_processed": True,
                    "video_id": video_id,
                    "canonical_url": canonical_url,
                }
            )
        )
        return

    clean_segments = data.get("segments", [])
    stitched_text, deduped_clean = stitch_segments(clean_segments)

    # Load raw transcript (parallel file in raw/ directory)
    raw_path = _find_raw_path(path)
    deduped_raw = None
    if raw_path:
        with open(raw_path, encoding="utf-8") as rf:
            raw_data = json.load(rf)
        _, deduped_raw = stitch_segments(raw_data.get("segments", []))

    chunks = chunk_segments(deduped_raw or deduped_clean, deduped_clean if deduped_raw else None)

    result = {
        "already_processed": False,
        "video_id": video_id,
        "channel_id": data.get("channel_id"),
        "title": data.get("title", f"YouTube video {video_id}"),
        "published_at": data.get("published_at"),
        "canonical_url": canonical_url,
        "stitched_text": stitched_text,
        "segment_count": len(deduped_clean),
        "chunks": chunks,
        "segments": [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in deduped_clean],
    }
    print(json.dumps(result, ensure_ascii=False))


def cmd_write(args: argparse.Namespace) -> None:
    """Persist Source, SourceDocument, SourceChunks, Entities, Claims, ClaimChunks."""
    path = Path(args.path)
    if not path.exists():
        print(json.dumps({"error": f"File not found: {path}"}))
        sys.exit(1)

    # Load claims from --claims or --claims-file
    if args.claims_file:
        with open(args.claims_file) as f:
            claims = json.load(f)
    elif args.claims:
        claims = json.loads(args.claims)
    else:
        print(json.dumps({"error": "Must provide --claims or --claims-file"}))
        sys.exit(1)

    # Re-load transcript to get metadata and re-stitch
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    clean_segments = data.get("segments", [])
    stitched_text, deduped_clean = stitch_segments(clean_segments)

    # Load raw transcript (parallel file in raw/ directory)
    raw_path = _find_raw_path(path)
    deduped_raw = None
    if raw_path:
        with open(raw_path, encoding="utf-8") as rf:
            raw_data = json.load(rf)
        _, deduped_raw = stitch_segments(raw_data.get("segments", []))

    chunks = chunk_segments(deduped_raw or deduped_clean, deduped_clean if deduped_raw else None)

    result = write_transcript(
        video_id=data["video_id"],
        title=data.get("title", f"YouTube video {data['video_id']}"),
        channel_id=data.get("channel_id", ""),
        published_at=data.get("published_at"),
        stitched_text=stitched_text,
        chunk_dicts=chunks,
        claims_json=claims,
    )

    print(json.dumps(result))


def cmd_update_transcript(args: argparse.Namespace) -> None:
    """Backfill clean_text on existing SourceChunks from a clean transcript JSON."""
    path = Path(args.path)
    if not path.exists():
        print(json.dumps({"error": f"File not found: {path}"}))
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    video_id = data["video_id"]
    canonical_url = f"https://youtube.com/watch?v={video_id}"

    # Stitch and dedup clean segments
    _, deduped_clean = stitch_segments(data.get("segments", []))

    session = SessionLocal()
    try:
        source = session.query(Source).filter(Source.canonical_url == canonical_url).first()
        if not source:
            print(json.dumps({"error": f"No source found for {canonical_url}"}))
            sys.exit(1)

        doc = session.query(SourceDocument).filter(SourceDocument.source_id == source.source_id).first()
        if not doc:
            print(json.dumps({"error": f"No document found for source {source.source_id}"}))
            sys.exit(1)

        chunks = (
            session.query(SourceChunk)
            .filter(SourceChunk.document_id == doc.document_id)
            .order_by(SourceChunk.chunk_index)
            .all()
        )

        updated = 0
        for chunk in chunks:
            idx = chunk.chunk_index
            if idx < len(deduped_clean):
                chunk.clean_text = deduped_clean[idx]["text"]
                updated += 1

        session.commit()
        print(
            json.dumps(
                {
                    "source_id": str(source.source_id),
                    "chunks_updated": updated,
                }
            )
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def cmd_reset(_args: argparse.Namespace) -> None:
    """Delete all claims, claim_chunks, source_chunks, and sources so transcripts can be re-ingested."""
    session = SessionLocal()
    try:
        cc_count = session.query(ClaimChunk).delete()
        c_count = session.query(Claim).delete()
        sc_count = session.query(SourceChunk).delete()
        doc_count = session.query(SourceDocument).delete()
        src_count = session.query(Source).delete()
        session.commit()
        print(
            json.dumps(
                {
                    "claim_chunks_deleted": cc_count,
                    "claims_deleted": c_count,
                    "source_chunks_deleted": sc_count,
                    "source_documents_deleted": doc_count,
                    "sources_deleted": src_count,
                }
            )
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Process YouTube transcript files")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # prepare subcommand
    prep = subparsers.add_parser("prepare", help="Stitch and chunk transcript")
    prep.add_argument("path", help="Path to transcript JSON file")

    # write subcommand
    write = subparsers.add_parser("write", help="Persist transcript and claims to DB")
    write.add_argument("path", help="Path to transcript JSON file")
    write.add_argument("--claims", help="Claims JSON string")
    write.add_argument("--claims-file", help="Path to claims JSON file")

    # update-transcript subcommand
    update = subparsers.add_parser(
        "update-transcript", help="Backfill clean_text on existing chunks from a clean transcript"
    )
    update.add_argument("path", help="Path to clean transcript JSON file")

    # reset subcommand
    subparsers.add_parser("reset", help="Delete all claims and claim_chunks from the database")

    args = parser.parse_args()

    if args.command == "prepare":
        cmd_prepare(args)
    elif args.command == "write":
        cmd_write(args)
    elif args.command == "update-transcript":
        cmd_update_transcript(args)
    elif args.command == "reset":
        cmd_reset(args)


if __name__ == "__main__":
    main()
