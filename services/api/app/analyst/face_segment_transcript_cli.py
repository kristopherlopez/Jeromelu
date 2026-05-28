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
import bisect
import json
import logging
import sys
from collections import defaultdict
from uuid import UUID

from jeromelu_shared.db import (
    Person,
    SessionLocal,
    Source,
    SourceDocument,
    SourceFaceCluster,
    SourceFaceDetection,
)
from jeromelu_shared.s3 import download_raw
from sqlalchemy.orm import Session

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

    Word-first algorithm — the right way to do this on multi-cam edited
    content where frame-aligned segments leave gaps that drop words:

      1. Load every face detection and bucket per ``frame_ts``.
      2. Compute the active-speaker cluster at each frame_ts (cluster
         with the highest ``mouth_opening`` that crosses the threshold;
         ``None`` if no face is above the threshold at that moment).
      3. Load every Deepgram word from the doc's transcript JSON.
      4. For each word, look up the active speaker at the word's start
         time (latest frame_ts <= word.start). Every word gets a
         speaker assignment (or ``None`` for "no face speaking").
      5. Group consecutive same-speaker words into segments —
         word-aligned start/end, no gaps.
      6. Smooth same-speaker segments across multi-cam camera cuts up
         to ``smooth_gap_seconds`` (a brief other-speaker run between
         two same-speaker runs collapses into one).
      7. Drop sub-``min_segment_seconds`` segments from the output (no
         re-attribution; just hide them).
    """
    doc = session.query(SourceDocument).filter(SourceDocument.source_id == source_id).first()
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

    # 2) Bucket by frame_ts. Multi-cam sources have multiple detections
    #    per frame (one per face on screen).
    by_frame: dict[float, list[tuple[int | None, float]]] = defaultdict(list)
    for r in rows:
        mo = float(r.mouth_opening) if r.mouth_opening is not None else 0.0
        by_frame[float(r.frame_ts)].append((r.cluster_id, mo))

    # 3) Per-frame active speaker: cluster with highest mouth_opening,
    #    provided it crosses the threshold. Otherwise NULL.
    sorted_frame_ts = sorted(by_frame.keys())
    per_frame_speaker: list[int | None] = []
    for ts in sorted_frame_ts:
        top_cid, top_mo = max(by_frame[ts], key=lambda t: t[1])
        per_frame_speaker.append(top_cid if (top_cid is not None and top_mo >= mouth_threshold) else None)

    # 4) Word-level transcript load.
    if doc.s3_key:
        try:
            dg = json.loads(download_raw(doc.s3_key))
            words = _deepgram_words_from_json(dg)
        except Exception:
            words = []
    else:
        words = []

    if not words:
        return []

    # 5) Word-first speaker lookup. For each word, the active speaker
    #    is whoever was speaking at the most recent face frame
    #    at-or-before word.start.
    def speaker_at(t: float) -> int | None:
        idx = bisect.bisect_right(sorted_frame_ts, t) - 1
        if idx < 0:
            # Word starts before any face frame was recorded — no signal
            # to attribute. Common for ~first few words if visual ID
            # warmed up after audio started.
            return None
        return per_frame_speaker[idx]

    word_speakers: list[tuple[float, float, str, int | None]] = []
    for w_start, w_end, w_text in words:
        word_speakers.append((w_start, w_end, w_text, speaker_at(w_start)))

    # 6) Group consecutive same-speaker words into segments.
    raw_segments: list[dict] = []
    cur: dict | None = None
    for w_start, w_end, w_text, speaker in word_speakers:
        if cur is not None and cur["speaker_cluster_id"] == speaker:
            cur["end"] = w_end
            cur["text"] = (cur["text"] + " " + w_text).strip() if w_text else cur["text"]
        else:
            if cur is not None:
                raw_segments.append(cur)
            cur = {
                "start": w_start,
                "end": w_end,
                "speaker_cluster_id": speaker,
                "text": w_text,
            }
    if cur is not None:
        raw_segments.append(cur)

    # 7) Smooth same-speaker runs separated by brief other-speaker cuts.
    #    Multi-cam editing flips between co-hosts every 2-3s during a
    #    single monologue — without smoothing, that monologue becomes a
    #    dozen short flips. Same logic as the old frame-aligned path,
    #    now over the word-aligned segments.
    smoothed: list[dict] = []
    for seg in raw_segments:
        if (
            smoothed
            and seg["speaker_cluster_id"] is not None
            and smoothed[-1]["speaker_cluster_id"] == seg["speaker_cluster_id"]
            and seg["start"] - smoothed[-1]["end"] <= smooth_gap_seconds
        ):
            smoothed[-1]["end"] = seg["end"]
            smoothed[-1]["text"] = (smoothed[-1]["text"] + " " + seg["text"]).strip()
        elif (
            seg["speaker_cluster_id"] is not None
            and len(smoothed) >= 2
            and smoothed[-1]["speaker_cluster_id"] is not None
            and smoothed[-1]["speaker_cluster_id"] != seg["speaker_cluster_id"]
            and smoothed[-2]["speaker_cluster_id"] == seg["speaker_cluster_id"]
            and (smoothed[-1]["end"] - smoothed[-1]["start"]) <= smooth_gap_seconds
            and seg["start"] - smoothed[-2]["end"] <= smooth_gap_seconds * 2
        ):
            # [A] [B short] [A] → collapse the B cut into the A around it.
            # Keep the interrupted-cluster's text in place (it was its
            # words); just extend the prior A and append this A's words.
            kept = smoothed[-1]
            smoothed.pop()
            smoothed[-1]["end"] = seg["end"]
            smoothed[-1]["text"] = (smoothed[-1]["text"] + " " + kept["text"] + " " + seg["text"]).strip()
        else:
            smoothed.append(seg)

    # 8) Drop tiny segments from the output. Don't re-attribute them
    #    to anyone — that risks lying about who spoke.
    merged = [s for s in smoothed if (s["end"] - s["start"]) >= min_segment_seconds or s["speaker_cluster_id"] is None]

    # 9) Resolve cluster_id → person_name via SourceFaceCluster + Person.
    cluster_meta = {
        c.cluster_id: c for c in session.query(SourceFaceCluster).filter(SourceFaceCluster.source_id == source_id).all()
    }
    person_ids = {c.attributed_person_id for c in cluster_meta.values() if c.attributed_person_id}
    person_name_by_id = (
        {p.person_id: p.canonical_name for p in session.query(Person).filter(Person.person_id.in_(person_ids)).all()}
        if person_ids
        else {}
    )

    for seg in merged:
        cid = seg["speaker_cluster_id"]
        if cid is None:
            seg["speaker_label"] = "—"
            seg["person_name"] = None
        else:
            cmeta = cluster_meta.get(cid)
            pid = cmeta.attributed_person_id if cmeta else None
            seg["speaker_label"] = f"FACE_{cid}"
            seg["person_name"] = person_name_by_id.get(pid) if pid else None

    return merged


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show what the transcript looks like if segmented purely "
        "by face presence + mouth opening (no pyannote).",
    )
    parser.add_argument("source_id", type=str, help="UUID of the sources row")
    parser.add_argument(
        "--mouth-threshold",
        type=float,
        default=DEFAULT_MOUTH_THRESHOLD,
        help=f"Mouth-opening floor for 'is speaking' (default {DEFAULT_MOUTH_THRESHOLD})",
    )
    parser.add_argument(
        "--min-segment",
        type=float,
        default=DEFAULT_MIN_SEGMENT_SECONDS,
        help=f"Drop segments shorter than this from output (default {DEFAULT_MIN_SEGMENT_SECONDS}s)",
    )
    parser.add_argument(
        "--smooth-gap",
        type=float,
        default=DEFAULT_SMOOTH_GAP_SECONDS,
        help=f"Merge same-speaker windows across multi-cam cuts up to this gap (default {DEFAULT_SMOOTH_GAP_SECONDS}s)",
    )
    parser.add_argument(
        "--include-silence",
        action="store_true",
        help="Include segments where no face is speaking (default: skip them)",
    )
    parser.add_argument(
        "--out",
        default="-",
        help="Output path (default '-' = stdout)",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
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
            session,
            source_id,
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
