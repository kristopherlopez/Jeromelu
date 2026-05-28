"""Context-aware transcript cleaner using traditional NLP techniques.

Pipeline:
  Step 0: Resolve round context + build scoped player pool
  Layer 1: Deterministic exact-match corrections
  Layer 1.5: Topic segmentation (keyword blocks for downstream chapter detection)
  Report: Confidence-tagged JSON report

Phonetic/fuzzy name corrections are intentionally NOT applied here.
They lack conversational context and produce false positives on common
English words (e.g. "Today" → "Todd", "Furious" → "Francis").
All fuzzy name resolution is deferred to the Phase 3 specialist agents
in the analyse-transcript pipeline, where each agent has chapter context
and a scoped player pool.

Usage:
  python scripts/clean_transcript.py data/transcripts/raw/CHANNEL_VIDEO.json
  python scripts/clean_transcript.py --all
  python scripts/clean_transcript.py --dry-run data/transcripts/raw/CHANNEL_VIDEO.json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from pathlib import Path

# Fix Windows console encoding for emoji/unicode
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from cleaning.context import (  # noqa: E402  # sys.path manipulation above must run first
    build_local_context,
    build_round_context,
)
from cleaning.deterministic import apply_deterministic, load_corrections  # noqa: E402
from cleaning.report import build_report, print_summary, write_report  # noqa: E402
from cleaning.segmentation import segment_transcript  # noqa: E402

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "transcripts" / "raw"
CLEAN_DIR = DATA_DIR / "transcripts" / "clean"
REPORTS_DIR = DATA_DIR / "transcripts" / "reports"


def clean_transcript(
    raw_path: Path,
    dry_run: bool = False,
) -> dict:
    """Run the deterministic cleaning pipeline on a single transcript.

    Phonetic/fuzzy corrections are deferred to the analyse-transcript
    pipeline where Phase 3 specialist agents have chapter context.

    Returns the cleaning report dict.
    """
    # Load raw transcript
    with open(raw_path, encoding="utf-8") as f:
        data = json.load(f)

    title = data.get("title", "")
    segments = data.get("segments", [])
    print(f"\nCleaning: {raw_path.name}")
    print(f"Title: {title}")
    print(f"Segments: {len(segments)}")

    # Step 0: Resolve round context
    round_context = build_round_context(title)
    print(f"Round: {round_context.round_num} ({round_context.confidence})")
    print(f"Primary players: {len(round_context.primary_players)}, Secondary: {len(round_context.secondary_players)}")

    # Layer 1: Deterministic corrections (exact match, 100% confidence)
    corrections = load_corrections()
    det_records = apply_deterministic(segments, corrections)
    print(f"Layer 1 (deterministic): {len(det_records)} corrections applied")

    # Step 0b: Build local context tracker
    _local_context, team_lookup = build_local_context()

    # Layer 1.5: Topic segmentation (after deterministic fixes clean up team names)
    topic_blocks = segment_transcript(segments, round_context, team_lookup)
    game_blocks = sum(1 for b in topic_blocks if b.block_type == "game")
    pos_blocks = sum(1 for b in topic_blocks if b.block_type == "position")
    gen_blocks = sum(1 for b in topic_blocks if b.block_type == "general")
    print(
        f"Layer 1.5 (segmentation): {len(topic_blocks)} blocks "
        f"({game_blocks} game, {pos_blocks} position, {gen_blocks} general)"
    )
    for block in topic_blocks:
        seg_count = block.end_idx - block.start_idx
        primary_count = sum(1 for p in (block.player_pool or []) if p.is_primary)
        print(
            f"  [{block.start_idx:4d}-{block.end_idx:4d}] "
            f"{block.block_type:8s} | {block.label:40s} | "
            f"{seg_count:4d} segs, {primary_count:3d} primary players"
        )

    # Build report (no phonetic records — fuzzy matching deferred to Phase 3)
    report = build_report(round_context, det_records, [], topic_blocks)
    print_summary(report)

    if dry_run:
        print("[DRY RUN] No files written.")
        return report

    # Write clean transcript
    clean_path = CLEAN_DIR / raw_path.name
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    with open(clean_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Clean transcript: {clean_path}")

    # Write report
    report_path = REPORTS_DIR / raw_path.with_suffix(".report.json").name
    write_report(report, report_path)
    print(f"Report: {report_path}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Context-aware transcript cleaner")
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to raw transcript JSON file",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Clean all raw transcripts in data/transcripts/raw/",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files",
    )

    args = parser.parse_args()

    if args.all:
        raw_files = sorted(RAW_DIR.glob("*.json"))
        if not raw_files:
            print(f"No JSON files found in {RAW_DIR}")
            sys.exit(1)
        print(f"Found {len(raw_files)} raw transcripts")
        for raw_path in raw_files:
            clean_transcript(raw_path, args.dry_run)
    elif args.path:
        raw_path = Path(args.path)
        if not raw_path.exists():
            print(f"File not found: {raw_path}")
            sys.exit(1)
        clean_transcript(raw_path, args.dry_run)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
