"""Unit tests for app.routers.admin pure helpers.

Covers segment stitching, chunk offset construction, sha256 checksum,
and word normalisation. The router endpoints themselves wrap DB writes
and belong in integration/.
"""

import hashlib

import pytest

from app.routers.admin import (
    _checksum,
    _chunk_segments,
    _normalize,
    _stitch_segments,
)


# ---------------------------------------------------------------------------
# _stitch_segments
# ---------------------------------------------------------------------------

class TestStitchSegments:
    def test_empty_input_returns_empty(self):
        text, segs = _stitch_segments([])
        assert text == ""
        assert segs == []

    def test_single_segment_returned_as_is(self):
        text, segs = _stitch_segments([{"start": 0, "end": 1, "text": "Hello"}])
        assert text == "Hello"
        assert len(segs) == 1
        assert segs[0]["text"] == "Hello"

    def test_multiple_segments_joined_with_space(self):
        text, segs = _stitch_segments([
            {"start": 0, "end": 1, "text": "Hello"},
            {"start": 1, "end": 2, "text": "world"},
        ])
        assert text == "Hello world"
        assert len(segs) == 2

    def test_segments_sorted_by_start(self):
        text, segs = _stitch_segments([
            {"start": 1, "end": 2, "text": "world"},
            {"start": 0, "end": 1, "text": "Hello"},
        ])
        assert text == "Hello world"
        assert segs[0]["start"] == 0
        assert segs[1]["start"] == 1

    def test_empty_text_segment_dropped(self):
        text, segs = _stitch_segments([
            {"start": 0, "end": 1, "text": "  "},
            {"start": 1, "end": 2, "text": "real"},
        ])
        assert text == "real"
        assert len(segs) == 1

    def test_fully_overlapping_segment_deduped(self):
        # Second segment is entirely inside the first — drop it.
        text, segs = _stitch_segments([
            {"start": 0, "end": 5, "text": "hello world"},
            {"start": 1, "end": 3, "text": "duplicate"},
        ])
        assert text == "hello world"
        assert len(segs) == 1

    def test_partial_overlap_extending_end_kept(self):
        # Second segment starts inside the first but extends past it —
        # keep both. Caller decides how to reconcile the overlap text.
        text, segs = _stitch_segments([
            {"start": 0, "end": 5, "text": "hello"},
            {"start": 3, "end": 8, "text": "lo world"},
        ])
        assert len(segs) == 2

    def test_double_arrow_caption_marker_removed(self):
        # YouTube auto-captions sprinkle ">>" speaker-change markers.
        text, _ = _stitch_segments([
            {"start": 0, "end": 1, "text": ">>Hello"},
        ])
        assert ">>" not in text

    def test_double_spaces_collapsed_after_join(self):
        text, _ = _stitch_segments([
            {"start": 0, "end": 1, "text": "a"},
            {"start": 1, "end": 2, "text": " b"},
        ])
        # The inner segment text gets stripped, then the join introduces
        # a single space between segments — no doubles should remain.
        assert "  " not in text

    def test_per_segment_text_stripped(self):
        _, segs = _stitch_segments([
            {"start": 0, "end": 1, "text": "  spaced  "},
        ])
        assert segs[0]["text"] == "spaced"


# ---------------------------------------------------------------------------
# _chunk_segments
# ---------------------------------------------------------------------------

class TestChunkSegments:
    def test_empty_input_returns_empty(self):
        assert _chunk_segments([]) == []

    def test_single_segment_offsets(self):
        chunks = _chunk_segments([{"start": 0.0, "end": 1.0, "text": "hello"}])
        assert len(chunks) == 1
        c = chunks[0]
        assert c["chunk_index"] == 0
        assert c["raw_text"] == "hello"
        assert c["clean_text"] is None
        assert c["start_ts"] == 0.0
        assert c["end_ts"] == 1.0
        assert c["start_offset"] == 0
        assert c["end_offset"] == 5  # len("hello")

    def test_multiple_segments_offsets_advance(self):
        chunks = _chunk_segments([
            {"start": 0.0, "end": 1.0, "text": "hi"},
            {"start": 1.0, "end": 2.0, "text": "world"},
        ])
        # Offsets account for an implicit single-space separator between
        # chunks: offset += len(raw) + 1.
        assert chunks[0]["start_offset"] == 0
        assert chunks[0]["end_offset"] == 2     # len("hi")
        assert chunks[1]["start_offset"] == 3   # 0 + 2 + 1
        assert chunks[1]["end_offset"] == 8     # 3 + len("world")

    def test_chunk_index_monotonic(self):
        chunks = _chunk_segments([
            {"start": 0.0, "end": 1.0, "text": "a"},
            {"start": 1.0, "end": 2.0, "text": "b"},
            {"start": 2.0, "end": 3.0, "text": "c"},
        ])
        assert [c["chunk_index"] for c in chunks] == [0, 1, 2]

    def test_clean_segments_aligned_by_index(self):
        chunks = _chunk_segments(
            [
                {"start": 0.0, "end": 1.0, "text": "raw1"},
                {"start": 1.0, "end": 2.0, "text": "raw2"},
            ],
            clean_segments=[
                {"text": "clean1"},
                {"text": "clean2"},
            ],
        )
        assert chunks[0]["clean_text"] == "clean1"
        assert chunks[1]["clean_text"] == "clean2"

    def test_clean_segments_shorter_than_raw_tolerated(self):
        # If cleaning failed past index N, those chunks should still emit
        # with clean_text=None rather than blowing up the ingest.
        chunks = _chunk_segments(
            [
                {"start": 0.0, "end": 1.0, "text": "raw1"},
                {"start": 1.0, "end": 2.0, "text": "raw2"},
                {"start": 2.0, "end": 3.0, "text": "raw3"},
            ],
            clean_segments=[{"text": "clean1"}],
        )
        assert chunks[0]["clean_text"] == "clean1"
        assert chunks[1]["clean_text"] is None
        assert chunks[2]["clean_text"] is None

    def test_timestamps_preserved_verbatim(self):
        chunks = _chunk_segments([
            {"start": 12.345, "end": 18.901, "text": "x"},
        ])
        assert chunks[0]["start_ts"] == 12.345
        assert chunks[0]["end_ts"] == 18.901


# ---------------------------------------------------------------------------
# _checksum
# ---------------------------------------------------------------------------

class TestChecksum:
    def test_empty_string_known_sha256(self):
        # sha256("") is a well-known constant.
        assert _checksum("") == hashlib.sha256(b"").hexdigest()

    def test_deterministic(self):
        assert _checksum("hello") == _checksum("hello")

    def test_different_input_different_hash(self):
        assert _checksum("hello") != _checksum("world")

    def test_hex_format_64_chars(self):
        h = _checksum("any text")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------

class TestNormalize:
    @pytest.mark.parametrize(
        "word,expected",
        [
            ("plain", "plain"),
            ("Hello!", "Hello"),
            ("(team)", "team"),
            ("[bracketed]", "bracketed"),
            ('"quoted"', "quoted"),
            ("Tom's", "Tom"),
            ("won't", "won"),
            ("they're", "they"),
            ("I've", "I"),
            ("we'll", "we"),
            ("I'd", "I"),
            ("I'm", "I"),
            ("Tom's.", "Tom"),
            ("end.", "end"),
            ("", ""),
        ],
    )
    def test_known_cases(self, word, expected):
        assert _normalize(word) == expected

    def test_only_first_matching_suffix_stripped(self):
        # The loop breaks on first match — so a contrived word ending in
        # multiple possessive markers loses just one.
        assert _normalize("foo's") == "foo"
