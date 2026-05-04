"""Side-by-side comparison of Deepgram and pyannote diarization.

The Phase 1 decision-gate evaluator. Reads both JSON artefacts for a
single source from S3 and prints:

    1. Summary stats (speakers, turns, duration).
    2. A confusion matrix (pyannote labels × Deepgram labels) showing
       seconds of co-occurrence at a sampled cadence.
    3. A greedy label alignment (pyannote → Deepgram) and the agreement
       percentage achieved after aligning labels.
    4. The first N disagreement timestamps (with --show-all-rows for
       the full sampled timeline).

Pure read; no DB writes, no S3 writes.

Usage:
    python -m app.analyst.diarize_compare <source_id>
    python -m app.analyst.diarize_compare <source_id> --interval 2.0
    python -m app.analyst.diarize_compare <source_id> --show-all-rows
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from jeromelu_shared.db import SessionLocal, Source
from jeromelu_shared.s3 import download_raw


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class Turn:
    start: float
    end: float
    speaker: str


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _deepgram_turns(deepgram: dict[str, Any]) -> list[Turn]:
    """Group consecutive same-speaker Deepgram utterances into turns."""
    utterances = deepgram.get("results", {}).get("utterances", []) or []
    turns: list[Turn] = []
    for u in utterances:
        speaker = u.get("speaker")
        if speaker is None:
            continue
        label = f"speaker_{speaker}"
        start = float(u["start"])
        end = float(u["end"])
        if turns and turns[-1].speaker == label and start - turns[-1].end < 1.0:
            turns[-1] = Turn(turns[-1].start, end, label)
        else:
            turns.append(Turn(start, end, label))
    return turns


def _pyannote_turns(pyannote: dict[str, Any]) -> list[Turn]:
    return [
        Turn(float(t["start"]), float(t["end"]), t["speaker"])
        for t in pyannote.get("turns", [])
    ]


def _speaker_at(turns: list[Turn], ts: float) -> str | None:
    """Linear scan for the speaker active at ts. Fine for sample sizes here."""
    for t in turns:
        if t.start <= ts < t.end:
            return t.speaker
    return None


def _load_json(s3_key: str) -> dict[str, Any] | None:
    try:
        return json.loads(download_raw(s3_key))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def _confusion(
    dg: list[Turn], pa: list[Turn], duration: float, interval: float,
) -> dict[tuple[str, str], int]:
    """Sample at `interval` and count co-occurrence of (pyannote, deepgram)
    speaker labels. Returns sample counts (multiply by interval for seconds)."""
    counts: dict[tuple[str, str], int] = {}
    ts = 0.0
    while ts < duration:
        d = _speaker_at(dg, ts)
        p = _speaker_at(pa, ts)
        if d and p:
            counts[(p, d)] = counts.get((p, d), 0) + 1
        ts += interval
    return counts


def _greedy_alignment(
    confusion: dict[tuple[str, str], int],
) -> dict[str, str]:
    """For each pyannote label, pick the Deepgram label with the largest
    co-occurrence count. Greedy, not Hungarian — fine for a sanity check."""
    pa_labels = {p for p, _ in confusion}
    mapping: dict[str, str] = {}
    for p in pa_labels:
        best = max(
            ((d, c) for (pp, d), c in confusion.items() if pp == p),
            key=lambda x: x[1],
            default=None,
        )
        if best:
            mapping[p] = best[0]
    return mapping


def _print_confusion_matrix(
    confusion: dict[tuple[str, str], int],
    interval: float,
) -> None:
    pa_labels = sorted({p for p, _ in confusion})
    dg_labels = sorted({d for _, d in confusion})
    if not pa_labels or not dg_labels:
        print("  (no co-occurrence — one diarizer produced no labels)")
        return

    pa_w = max(len(p) for p in pa_labels)
    pa_w = max(pa_w, len("pyannote \\ deepgram"))
    cell_w = max(8, max(len(d) for d in dg_labels))

    header = " " * pa_w + " | " + " | ".join(f"{d:>{cell_w}}" for d in dg_labels)
    print(header)
    print("-" * len(header))
    for p in pa_labels:
        row = f"{p:<{pa_w}} | "
        cells = []
        for d in dg_labels:
            secs = confusion.get((p, d), 0) * interval
            cells.append(f"{secs:>{cell_w}.0f}")
        row += " | ".join(cells)
        print(row)
    print("  (cells = seconds of co-occurrence at sampled cadence)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare Deepgram vs pyannote diarization for one source.",
    )
    parser.add_argument("source_id", type=str)
    parser.add_argument(
        "--interval", type=float, default=2.0,
        help="Sampling interval in seconds (default 2.0)",
    )
    parser.add_argument(
        "--max-disagreements", type=int, default=30,
        help="How many disagreement rows to print (default 30)",
    )
    parser.add_argument(
        "--show-all-rows", action="store_true",
        help="Print every sample row, not just disagreements after alignment",
    )
    args = parser.parse_args()

    try:
        source_id = UUID(args.source_id)
    except ValueError:
        print(f"Invalid UUID: {args.source_id}", file=sys.stderr)
        return 2

    with SessionLocal() as session:
        source = (
            session.query(Source)
            .filter(Source.source_id == source_id)
            .one_or_none()
        )
        if source is None:
            print(f"No source with id {source_id}", file=sys.stderr)
            return 2
        if not source.audio_s3_key:
            print("Source has no audio_s3_key", file=sys.stderr)
            return 1
        audio_key = source.audio_s3_key
        title = source.title

    if audio_key.endswith(".m4a"):
        deepgram_key = audio_key[: -len(".m4a")] + ".deepgram.json"
        pyannote_key = audio_key[: -len(".m4a")] + ".pyannote.json"
    else:
        deepgram_key = audio_key + ".deepgram.json"
        pyannote_key = audio_key + ".pyannote.json"

    print(f"Source: {source_id}")
    print(f"  title:        {title}")
    print(f"  audio_s3_key: {audio_key}")
    print()

    deepgram = _load_json(deepgram_key)
    pyannote = _load_json(pyannote_key)

    if deepgram is None:
        print(f"WARN: Deepgram JSON not found at {deepgram_key}")
    if pyannote is None:
        print(f"ERROR: pyannote JSON not found at {pyannote_key}")
        print(f"Run `make diarize SOURCE_ID={source_id}` first.")
        return 1
    if deepgram is None:
        print("Cannot compare without Deepgram JSON.")
        return 1

    dg_turns = _deepgram_turns(deepgram)
    pa_turns = _pyannote_turns(pyannote)

    dg_speakers = sorted({t.speaker for t in dg_turns})
    pa_speakers = sorted({t.speaker for t in pa_turns})

    duration = max(
        max((t.end for t in dg_turns), default=0.0),
        max((t.end for t in pa_turns), default=0.0),
    )

    print("=== Summary ===")
    print(f"{'':12} {'Deepgram':>14} {'pyannote':>14}")
    print(f"{'speakers':12} {len(dg_speakers):>14} {len(pa_speakers):>14}")
    print(f"{'turns':12} {len(dg_turns):>14} {len(pa_turns):>14}")
    print(f"{'duration':12} {duration:>14.1f}s")
    print(f"  deepgram speakers: {dg_speakers}")
    print(f"  pyannote speakers: {pa_speakers}")
    print()

    confusion = _confusion(dg_turns, pa_turns, duration, args.interval)
    print(f"=== Confusion matrix (sampled every {args.interval}s) ===")
    _print_confusion_matrix(confusion, args.interval)
    print()

    mapping = _greedy_alignment(confusion)
    print("=== Greedy label alignment (pyannote -> Deepgram) ===")
    for p, d in sorted(mapping.items()):
        print(f"  {p}  ->  {d}")
    print()

    # Agreement % after alignment
    ts = 0.0
    agree = 0
    total = 0
    disagreements: list[tuple[float, str, str, str]] = []
    while ts < duration:
        d = _speaker_at(dg_turns, ts)
        p = _speaker_at(pa_turns, ts)
        if d and p:
            total += 1
            mapped = mapping.get(p)
            if mapped == d:
                agree += 1
            else:
                disagreements.append((ts, d, p, mapped or "-"))
        ts += args.interval

    pct = (100.0 * agree / total) if total else 0.0
    print(f"=== Agreement: {agree}/{total} samples ({pct:.1f}%) ===")
    print()

    if args.show_all_rows:
        print("=== Full sampled timeline ===")
        print(f"{'time':>9} {'Deepgram':>12} {'pyannote':>14} {'pa->dg':>12}")
        ts = 0.0
        while ts < duration:
            d = _speaker_at(dg_turns, ts) or "-"
            p = _speaker_at(pa_turns, ts) or "-"
            mapped = mapping.get(p, "-")
            print(f"{ts:>9.1f} {d:>12} {p:>14} {mapped:>12}")
            ts += args.interval
    else:
        n = min(args.max_disagreements, len(disagreements))
        print(f"=== First {n} disagreements (after alignment) ===")
        print(f"{'time':>9} {'Deepgram':>12} {'pyannote':>14} {'mapped':>12}")
        for ts, d, p, mapped in disagreements[:n]:
            print(f"{ts:>9.1f} {d:>12} {p:>14} {mapped:>12}")
        if len(disagreements) > n:
            print(f"  ... {len(disagreements) - n} more")

    return 0


if __name__ == "__main__":
    sys.exit(main())
