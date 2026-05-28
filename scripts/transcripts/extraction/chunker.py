"""Map each deduped transcript segment to a single source chunk."""


def chunk_segments(
    raw_segments: list[dict],
    clean_segments: list[dict] | None = None,
) -> list[dict]:
    """Create one chunk per segment, with raw_text and clean_text.

    raw_segments and clean_segments must be aligned 1:1 (same timestamps).
    If clean_segments is None, clean_text is left empty.

    Each chunk records: chunk_index, raw_text, clean_text, start_ts, end_ts,
    start_offset, end_offset.
    """
    if not raw_segments:
        return []

    chunks: list[dict] = []
    text_offset = 0

    for i, seg in enumerate(raw_segments):
        raw = seg["text"]
        clean = clean_segments[i]["text"] if clean_segments and i < len(clean_segments) else None
        chunks.append(
            {
                "chunk_index": i,
                "raw_text": raw,
                "clean_text": clean,
                "start_ts": seg["start"],
                "end_ts": seg["end"],
                "start_offset": text_offset,
                "end_offset": text_offset + len(raw),
            }
        )
        text_offset += len(raw) + 1  # +1 for inter-segment space

    return chunks
