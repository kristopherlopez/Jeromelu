"""Stitch overlapping YouTube auto-caption segments into clean text."""


def stitch_segments(segments: list[dict]) -> tuple[str, list[dict]]:
    """Sort segments by start time, merge overlaps, return (text, deduped_segments).

    YouTube auto-captions frequently overlap — a segment ending at 4.4s may
    overlap with one starting at 2.08s. We deduplicate by tracking the last
    emitted end-time and skipping segments whose text is already covered.
    """
    if not segments:
        return "", []

    sorted_segs = sorted(segments, key=lambda s: s["start"])

    deduped: list[dict] = []
    last_end = -1.0

    for seg in sorted_segs:
        start = seg["start"]
        end = seg["end"]
        text = seg["text"].strip()

        if not text:
            continue

        # Skip segments that are fully contained within already-processed range
        if start < last_end:
            # Partial overlap — only take if it extends past last_end
            if end <= last_end:
                continue
            # Keep it but note the overlap
        deduped.append(
            {
                "start": start,
                "end": end,
                "text": text,
            }
        )
        last_end = max(last_end, end)

    # Build stitched text
    full_text = " ".join(seg["text"] for seg in deduped)
    # Clean up double spaces and ">>" markers from auto-captions
    full_text = full_text.replace(">>", "").replace("  ", " ").strip()

    return full_text, deduped
