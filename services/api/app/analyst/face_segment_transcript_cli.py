"""Face-driven transcript segmentation — exploratory CLI.

Bypasses pyannote entirely. Walks face detections frame-by-frame,
picks the active speaker per frame using the existing mouth-opening
ASD signal, groups consecutive frames into segments, and attaches the
overlapping Deepgram chunk text to each segment.

Usage:
    python -m app.analyst.face_segment_transcript_cli <source_id>
    python -m app.analyst.face_segment_transcript_cli <source_id> --min-segment 0.5
    python -m app.analyst.face_segment_transcript_cli <source_id> --mouth-threshold 0.045
    python -m app.analyst.face_segment_transcript_cli <source_id> --out transcript.md

Stdout (default) gets a markdown-style transcript:

    [00:01:23 - 00:01:31] FACE_4 → Andrew Voss
      "Welcome back to the round 10 preview show..."

    [00:01:31 - 00:01:34] FACE_1
      "Yeah I think the Cowboys are going..."
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from uuid import UUID

from sqlalchemy.orm import Session

from jeromelu_shared.db import (
    Person,
    SessionLocal,
    Source,
    SourceDocument,
    SourceFaceCluster,
    SourceFaceDetection,
)
from jeromelu_shared.s3 import download_raw


#: Same default the live ASD path uses (visual_id.MIN_ACTIVE_MOUTH_OPENING).
DEFAULT_MOUTH_THRESHOLD = 0.045

#: Two same-speaker windows separated by a gap of at most this long get
#: merged into one segment. Multi-cam edits cut between co-hosts every
#: 2-3 seconds during a single monologue; without smoothing, the same
#: monologue gets split into a dozen short "speaker A / speaker B"
#: segments. Default is conservative (3s) so genuine speaker turns
#: aren't merged.
DEFAULT_SMOOTH_GAP_SECONDS = 3.0

#: Segments shorter than this after smoothing are dropped from the
#: output (just hidden — they don't get re-attributed to anyone). Helps
#: cut single-frame mouth-opening flickers from background faces.
DEFAULT_MIN_SEGMENT_SECONDS = 1.0


def _fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _deepgram_words_from_json(doc: dict) -> list[tuple[float, float, str]]:
    """Extract (start, end, word) tuples from a Deepgram nova-3 JSON.

    Returns words in chronological order. Defensively handles missing
    channels/alternatives so a malformed JSON yields ``[]`` instead of
    crashing the whole segmentation.
    """
    out: list[tuple[float, float, str]] = []
    channels = (doc.get("results") or {}).get("channels") or []
    if not channels:
        return out
    alts = channels[0].get("alternatives") or []
    if not alts:
        return out
    for w in alts[0].get("words") or []:
        try:
            out.append((float(w["start"]), float(w["end"]), str(w.get("punctuated_word") or w.get("word") or "")))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def segment_by_face(
    session: Session,
    source_id: UUID,
    *,
    mouth_threshold: float,
    smooth_gap_seconds: float,
    min_segment_seconds: float,
) -> list[dict]:
    """Produce face-driven transcript segments for ``source_id``.

    Returns one segment per contiguous run of frames with the same
    active-speaker cluster_id. Each segment carries the time range, the
    speaker (cluster_id + optional attributed person), and the
    concatenated text of every Deepgram chunk that overlaps the range.
    """
    doc = (
        session.query(SourceDocument)
        .filter(SourceDocument.source_id == source_id)
        .first()
    )
    if not doc:
        return []

    # 1) Load every detection. ~14k rows × 4 floats — trivial.
    rows = (
        session.query(
            SourceFaceDetection.frame_ts,
            SourceFaceDetection.cluster_id,
            SourceFaceDetection.mouth_opening,
        )
        .filter(SourceFaceDetection.source_id == source_id)
        .order_by(SourceFaceDetection.frame_ts)
        .all()
    )
    if not rows:
        return []

    # 2) Bucket by frame_ts — at multi-cam sources there are usually
    #    multiple detections per frame (one per face on screen).
    by_frame: dict[float, list[tuple[int | None, float]]] = defaultdict(list)
    for r in rows:
        mo = float(r.mouth_opening) if r.mouth_opening is not None else 0.0
        by_frame[float(r.frame_ts)].append((r.cluster_id, mo))

    # 3) Per-frame active speaker: cluster with highest mouth_opening,
    #    provided it crosses the threshold. Otherwise NULL (silence /
    #    everyone closed-mouth).
    per_frame_speaker: list[tuple[float, int | None]] = []
    for ts in sorted(by_frame.keys()):
        ranked = sorted(by_frame[ts], key=lambda t: -t[1])
        top_cid, top_mo = ranked[0]
        speaker = top_cid if (top_cid is not None and top_mo >= mouth_threshold) else None
        per_frame_speaker.append((ts, speaker))

    # 4) Group consecutive same-speaker frames into raw segments.
    raw_segments: list[dict] = []
    cur_speaker: int | None = -2  # sentinel so first frame always opens
    cur_start: float = 0.0
    cur_last: float = 0.0
    for ts, speaker in per_frame_speaker:
        if speaker != cur_speaker:
            if raw_segments or cur_speaker != -2:
                raw_segments.append({
                    "start": cur_start,
                    "end": cur_last,
                    "speaker_cluster_id": cur_speaker,
                })
            cur_speaker = speaker
            cur_start = ts
        cur_last = ts
    raw_segments.append({
        "start": cur_start,
        "end": cur_last,
        "speaker_cluster_id": cur_speaker,
    })

    # 5) Smooth across short camera cuts: merge same-speaker segments
    #    separated by a gap of at most ``smooth_gap_seconds``. Multi-cam
    #    edits flip between co-hosts every 2-3s during a single
    #    monologue — without smoothing, that monologue becomes a dozen
    #    short flips. We only merge across other speakers, not silence
    #    (silence is genuine information — someone took a breath).
    smoothed: list[dict] = []
    for seg in raw_segments:
        if (
            smoothed
            and seg["speaker_cluster_id"] is not None
            and smoothed[-1]["speaker_cluster_id"] == seg["speaker_cluster_id"]
            and seg["start"] - smoothed[-1]["end"] <= smooth_gap_seconds
        ):
            smoothed[-1]["end"] = seg["end"]
        else:
            # Also walk backwards to absorb a same-speaker run that was
            # interrupted by a brief other-speaker cut. E.g. [A 5s] [B 1s] [A 4s]
            # becomes [A 10s] because the B cut was a multi-cam flash.
            if (
                seg["speaker_cluster_id"] is not None
                and len(smoothed) >= 2
                and smoothed[-1]["speaker_cluster_id"] is not None
                and smoothed[-1]["speaker_cluster_id"] != seg["speaker_cluster_id"]
                and smoothed[-2]["speaker_cluster_id"] == seg["speaker_cluster_id"]
                and (smoothed[-1]["end"] - smoothed[-1]["start"]) <= smooth_gap_seconds
                and seg["start"] - smoothed[-2]["end"] <= smooth_gap_seconds * 2
            ):
                # Drop the brief interruption, extend the prior same-speaker.
                smoothed.pop()
                smoothed[-1]["end"] = seg["end"]
            else:
                smoothed.append(seg)

    # 6) Drop tiny segments from the output (just filter; don't
    #    re-attribute them to anyone — that risks lying about who spoke).
    merged = [s for s in smoothed if (s["end"] - s["start"]) >= min_segment_seconds or s["speaker_cluster_id"] is None]

    # 6) Resolve cluster_id → person_name via SourceFaceCluster + Person.
    cluster_meta = {
        c.cluster_id: c
        for c in session.query(SourceFaceCluster)
        .filter(SourceFaceCluster.source_id == source_id)
        .all()
    }
    person_ids = {
        c.attributed_person_id for c in cluster_meta.values() if c.attributed_person_id
    }
    person_name_by_id = {
        p.person_id: p.canonical_name
        for p in session.query(Person).filter(Person.person_id.in_(person_ids)).all()
    } if person_ids else {}

    # 7) Word-level transcript matching. Sentence-level utterances are
    #    too coarse: a single utterance often spans multiple face
    #    segments after a camera cut, and chunk.start_ts can fall
    #    outside the segment that actually holds the spoken words.
    #    Load the Deepgram JSON once and bucket each word into the
    #    segment whose time range contains its start.
    if doc.s3_key:
        try:
            dg = json.loads(download_raw(doc.s3_key))
            words = _deepgram_words_from_json(dg)
        except Exception:
            words = []
    else:
        words = []

    for seg in merged:
        seg["text"] = ""
        cid = seg["speaker_cluster_id"]
        if cid is None:
            seg["speaker_label"] = "—"
            seg["person_name"] = None
        else:
            cmeta = cluster_meta.get(cid)
            pid = cmeta.attributed_person_id if cmeta else None
            seg["speaker_label"] = f"FACE_{cid}"
            seg["person_name"] = person_name_by_id.get(pid) if pid else None

    # Two-pointer walk: words and segments are both sorted by start.
    # Each word lands in the first segment whose [start, end) contains
    # its start timestamp.
    seg_idx = 0
    for w_start, _w_end, w_text in words:
        while seg_idx < len(merged) and merged[seg_idx]["end"] <= w_start:
            seg_idx += 1
        if seg_idx >= len(merged):
            break
        if merged[seg_idx]["start"] <= w_start < merged[seg_idx]["end"]:
            sep = " " if merged[seg_idx]["text"] else ""
            merged[seg_idx]["text"] = merged[seg_idx]["text"] + sep + w_text

    return merged


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show what the transcript looks like if segmented purely "
                    "by face presence + mouth opening (no pyannote).",
    )
    parser.add_argument("source_id", type=str, help="UUID of the sources row")
    parser.add_argument(
        "--mouth-threshold", type=float, default=DEFAULT_MOUTH_THRESHOLD,
        help=f"Mouth-opening floor for 'is speaking' (default {DEFAULT_MOUTH_THRESHOLD})",
    )
    parser.add_argument(
        "--min-segment", type=float, default=DEFAULT_MIN_SEGMENT_SECONDS,
        help=f"Drop segments shorter than this from output (default {DEFAULT_MIN_SEGMENT_SECONDS}s)",
    )
    parser.add_argument(
        "--smooth-gap", type=float, default=DEFAULT_SMOOTH_GAP_SECONDS,
        help=f"Merge same-speaker windows across multi-cam cuts up to this gap (default {DEFAULT_SMOOTH_GAP_SECONDS}s)",
    )
    parser.add_argument(
        "--include-silence", action="store_true",
        help="Include segments where no face is speaking (default: skip them)",
    )
    parser.add_argument(
        "--out", default="-",
        help="Output path (default '-' = stdout)",
    )
    parser.add_argument(
        "--log-level", default="WARNING",
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
        source = session.query(Source).filter(Source.source_id == source_id).one_or_none()
        if source is None:
            print(f"No source with id {source_id}", file=sys.stderr)
            return 2
        segments = segment_by_face(
            session, source_id,
            mouth_threshold=args.mouth_threshold,
            smooth_gap_seconds=args.smooth_gap,
            min_segment_seconds=args.min_segment,
        )

    if not segments:
        print(f"No face detections for source {source_id} — nothing to segment.", file=sys.stderr)
        return 1

    lines: list[str] = []
    lines.append(f"# Face-driven transcript: {source.title}")
    lines.append("")
    lines.append(
        f"_Source `{source_id}` · "
        f"mouth threshold {args.mouth_threshold} · "
        f"min segment {args.min_segment}s · "
        f"{len(segments)} segments_"
    )
    lines.append("")

    shown = 0
    skipped_silence = 0
    for seg in segments:
        if seg["speaker_cluster_id"] is None and not args.include_silence:
            skipped_silence += 1
            continue
        rng = f"[{_fmt_ts(seg['start'])} - {_fmt_ts(seg['end'])}]"
        if seg["speaker_cluster_id"] is None:
            header = f"{rng} — _no face speaking_"
        else:
            header = f"{rng} {seg['speaker_label']}"
            if seg["person_name"]:
                header += f" → **{seg['person_name']}**"
        lines.append(header)
        if seg["text"]:
            lines.append(f"  > {seg['text']}")
        else:
            lines.append("  > _(no transcript text in this window)_")
        lines.append("")
        shown += 1

    if not args.include_silence and skipped_silence:
        lines.append(f"_(skipped {skipped_silence} silence segments; pass --include-silence to show)_")

    out = "\n".join(lines)
    if args.out == "-":
        # Force utf-8 on Windows so the em-dash / arrows survive cp1252 stdout.
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(out)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"Wrote {shown} segments to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
