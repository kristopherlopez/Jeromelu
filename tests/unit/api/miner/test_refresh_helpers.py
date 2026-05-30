"""Unit tests for app.miner.youtube.refresh pure helpers.

Covers YouTube URL → video-id parsing, the RFC 3339 timestamp parser, and the
change-only-storage change-detection predicate. The DB-backed cursor +
enumeration + latest-metrics-loader logic belongs in integration/.
"""

from datetime import UTC, datetime

import pytest
from app.miner.youtube.refresh import (
    _metrics_changed,
    _parse_published_at,
    _video_id_from_url,
)

# ---------------------------------------------------------------------------
# _video_id_from_url
# ---------------------------------------------------------------------------


class TestVideoIdFromUrl:
    @pytest.mark.parametrize(
        "url,expected",
        [
            # Standard watch URL
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            # Without https
            ("http://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            # Bare youtube.com (no www)
            ("https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            # Short-form youtu.be
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            # With timestamp + extra params after the id
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ?t=42", "dQw4w9WgXcQ"),
            # Embed-style URLs that share the v= pattern
            ("https://www.youtube.com/embed?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ],
    )
    def test_extracts_id_from_known_shapes(self, url, expected):
        assert _video_id_from_url(url) == expected

    def test_id_must_be_exactly_eleven_chars(self):
        # YouTube IDs are always 11 chars — anything shorter shouldn't match.
        assert _video_id_from_url("https://youtu.be/short") is None

    def test_id_with_underscores_and_hyphens_kept(self):
        # The character set [A-Za-z0-9_-] is part of the id grammar.
        assert _video_id_from_url("https://youtu.be/aBc-De_FgHi") == "aBc-De_FgHi"

    def test_returns_none_for_blank(self):
        assert _video_id_from_url("") is None
        assert _video_id_from_url(None) is None

    def test_returns_none_when_no_id_present(self):
        assert _video_id_from_url("https://example.com/somepage") is None


# ---------------------------------------------------------------------------
# _parse_published_at
# ---------------------------------------------------------------------------


class TestParsePublishedAt:
    def test_z_suffix_parsed_as_utc(self):
        result = _parse_published_at("2026-04-29T08:30:00Z")
        assert result == datetime(2026, 4, 29, 8, 30, 0, tzinfo=UTC)

    def test_explicit_offset_preserved(self):
        result = _parse_published_at("2026-04-29T08:30:00+10:00")
        assert result is not None
        assert result.utcoffset().total_seconds() == 10 * 3600

    def test_fractional_seconds_supported(self):
        result = _parse_published_at("2026-04-29T08:30:00.123456Z")
        assert result is not None
        assert result.microsecond == 123456

    def test_blank_returns_none(self):
        assert _parse_published_at("") is None
        assert _parse_published_at(None) is None

    def test_unparseable_returns_none_not_raises(self):
        # Defensive: API drift shouldn't crash the cursor.
        assert _parse_published_at("not a date") is None
        assert _parse_published_at("2026/04/29") is None


# ---------------------------------------------------------------------------
# _metrics_changed — change-only storage predicate
# ---------------------------------------------------------------------------


class TestMetricsChanged:
    def test_no_prior_snapshot_records(self):
        # First-ever sample for a video/channel — always record.
        assert _metrics_changed(None, {"views": 100, "likes": 5, "comments": 2}) is True

    def test_identical_payload_skips(self):
        prev = {"views": 100, "likes": 5, "comments": 2}
        curr = {"views": 100, "likes": 5, "comments": 2}
        assert _metrics_changed(prev, curr) is False

    def test_changed_value_records(self):
        prev = {"views": 100, "likes": 5, "comments": 2}
        curr = {"views": 101, "likes": 5, "comments": 2}
        assert _metrics_changed(prev, curr) is True

    def test_different_key_set_records(self):
        # e.g. comments get disabled and the field drops out of the payload.
        prev = {"views": 100, "likes": 5, "comments": 0}
        curr = {"views": 100, "likes": 5}
        assert _metrics_changed(prev, curr) is True

    def test_reordered_keys_same_content_skips(self):
        # JSONB round-trips key order; dict equality is order-independent.
        prev = {"comments": 2, "likes": 5, "views": 100}
        curr = {"views": 100, "likes": 5, "comments": 2}
        assert _metrics_changed(prev, curr) is False

    def test_channel_payload_shape_supported(self):
        # The predicate is shape-agnostic — works for the channel payload too.
        prev = {"subscribers": 1000, "videos": 50, "views": 9999, "country": "AU"}
        assert _metrics_changed(prev, dict(prev)) is False
        assert _metrics_changed(prev, {**prev, "subscribers": 1001}) is True
