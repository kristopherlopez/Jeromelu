"""Layer 3: Confidence tagging and report generation."""

from __future__ import annotations

import json
from pathlib import Path

from .context import RoundContext
from .segmentation import TopicBlock


def build_report(
    round_context: RoundContext,
    deterministic_records: list[dict],
    phonetic_records: list[dict],
    topic_blocks: list[TopicBlock] | None = None,
) -> dict:
    """Build a cleaning report from all correction records."""
    applied = []
    flagged = []

    # All deterministic corrections are applied (HIGH confidence)
    for rec in deterministic_records:
        applied.append(rec)

    # Phonetic: MEDIUM are applied, LOW are flagged
    for rec in phonetic_records:
        if rec["confidence"] == "MEDIUM":
            applied.append(rec)
        else:
            flagged.append(rec)

    # Stats
    stats = {
        "high": sum(1 for r in applied if r["confidence"] == "HIGH"),
        "medium": sum(1 for r in applied if r["confidence"] == "MEDIUM"),
        "low": len([r for r in flagged if r["confidence"] == "LOW"]),
        "flagged": len([r for r in flagged if r["confidence"] == "FLAGGED"]),
        "total_applied": len(applied),
        "total_flagged": len(flagged),
    }

    # Deduplicate applied for summary (same original→corrected pair)
    seen_applied: dict[str, dict] = {}
    for rec in applied:
        key = f"{rec['original']}→{rec.get('corrected', '')}"
        if key in seen_applied:
            seen_applied[key]["count"] = seen_applied[key].get("count", 1) + 1
        else:
            seen_applied[key] = {**rec, "count": 1}

    # Build segments summary
    segments_summary = []
    if topic_blocks:
        for block in topic_blocks:
            primary_count = sum(1 for p in (block.player_pool or []) if p.is_primary)
            segments_summary.append({
                "start_idx": block.start_idx,
                "end_idx": block.end_idx,
                "block_type": block.block_type,
                "label": block.label,
                "teams": block.teams,
                "positions": block.positions,
                "segment_count": block.end_idx - block.start_idx,
                "primary_players": primary_count,
            })

    return {
        "context": {
            "round": round_context.round_num,
            "teams_playing": round_context.teams_playing,
            "byes": round_context.bye_teams,
            "confidence": round_context.confidence,
        },
        "topic_segments": segments_summary,
        "corrections_applied": list(seen_applied.values()),
        "flagged_for_review": flagged,
        "stats": stats,
    }


def write_report(report: dict, output_path: Path) -> None:
    """Write cleaning report to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def print_summary(report: dict) -> None:
    """Print a human-readable summary to stdout."""
    stats = report["stats"]
    ctx = report["context"]

    print(f"\n{'='*60}")
    print(f"CLEANING REPORT")
    print(f"{'='*60}")

    if ctx["round"]:
        print(f"Round: {ctx['round']} ({ctx['confidence']} confidence)")
        print(f"Teams: {len(ctx['teams_playing'])} playing, {len(ctx['byes'])} on bye")
    else:
        print(f"Round: not identified (fallback mode)")

    if report.get("topic_segments"):
        segs = report["topic_segments"]
        game_count = sum(1 for s in segs if s["block_type"] == "game")
        pos_count = sum(1 for s in segs if s["block_type"] == "position")
        gen_count = sum(1 for s in segs if s["block_type"] == "general")
        print(f"\nTopic segments: {len(segs)} blocks "
              f"({game_count} game, {pos_count} position, {gen_count} general)")

    print(f"\nCorrections applied: {stats['total_applied']}")
    print(f"  HIGH (deterministic): {stats['high']}")
    print(f"  MEDIUM (phonetic):    {stats['medium']}")
    print(f"\nFlagged for review: {stats['total_flagged']}")
    print(f"  LOW (near threshold): {stats['low']}")

    if report["corrections_applied"]:
        print(f"\n--- Top corrections ---")
        # Show unique corrections sorted by count
        sorted_corrs = sorted(
            report["corrections_applied"],
            key=lambda x: x.get("count", 1),
            reverse=True,
        )
        for rec in sorted_corrs[:20]:
            count = rec.get("count", 1)
            conf = rec["confidence"]
            print(f"  [{conf}] {rec['original']!r} → {rec.get('corrected', '?')!r} (×{count})")

    if report["flagged_for_review"]:
        print(f"\n--- Flagged for review ---")
        for rec in report["flagged_for_review"][:10]:
            best = rec.get("best_match", "?")
            score = rec.get("score", 0)
            print(f"  {rec['original']!r} → {best!r}? (score: {score:.3f})")

    print(f"{'='*60}\n")
