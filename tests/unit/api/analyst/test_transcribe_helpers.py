"""Unit tests for app.analyst.transcribe_helpers.

Covers Deepgram dict accessors, S3 key derivation, NaN/inf embedding
guard, and the timestamp-overlap turn picker. The helpers module is
deliberately split out of transcribe.py so this test never imports
diarize → pyannote → torch.
"""

from app.analyst.transcribe_helpers import (
    audio_duration,
    max_overlap_turn,
    request_id,
    safe_embedding,
    transcript_s3_key_from_audio,
    utterances,
)
from jeromelu_shared.db import SourceSpeaker

# ---------------------------------------------------------------------------
# transcript_s3_key_from_audio
# ---------------------------------------------------------------------------


class TestTranscriptS3KeyFromAudio:
    def test_m4a_replaced_with_deepgram_json(self):
        result = transcript_s3_key_from_audio("youtube/UCxxx/abc123.m4a")
        assert result == "youtube/UCxxx/abc123.deepgram.json"

    def test_non_m4a_appends_suffix(self):
        # Defensive: if Miner ever stores audio under a different extension
        # the key still derives uniquely (no clobber of a real .m4a path).
        result = transcript_s3_key_from_audio("youtube/UCxxx/abc123.wav")
        assert result == "youtube/UCxxx/abc123.wav.deepgram.json"

    def test_only_trailing_m4a_stripped(self):
        # Path containing 'm4a' as a directory name shouldn't be mangled.
        result = transcript_s3_key_from_audio("m4a/sub/abc123.m4a")
        assert result == "m4a/sub/abc123.deepgram.json"


# ---------------------------------------------------------------------------
# safe_embedding
# ---------------------------------------------------------------------------


class TestSafeEmbedding:
    def test_none_passthrough(self):
        assert safe_embedding(None) is None

    def test_clean_floats_returned_unchanged(self):
        emb = [0.1, -0.2, 3.14, 0.0]
        assert safe_embedding(emb) == emb

    def test_ints_acceptable(self):
        # Embeddings are usually float, but ints are finite numbers too.
        assert safe_embedding([1, 2, 3]) == [1, 2, 3]

    def test_nan_rejected(self):
        # pgvector won't store NaN — the whole embedding is dropped.
        assert safe_embedding([0.1, float("nan"), 0.3]) is None

    def test_positive_inf_rejected(self):
        assert safe_embedding([0.1, float("inf"), 0.3]) is None

    def test_negative_inf_rejected(self):
        assert safe_embedding([0.1, float("-inf"), 0.3]) is None

    def test_non_numeric_rejected(self):
        # Defensive against mangled JSON.
        assert safe_embedding([0.1, "string", 0.3]) is None


# ---------------------------------------------------------------------------
# max_overlap_turn
# ---------------------------------------------------------------------------


def _turn(start: float, end: float, label: str = "SPEAKER_00") -> SourceSpeaker:
    """Construct an in-memory SourceSpeaker with just the fields the
    overlap helper reads. No DB required."""
    return SourceSpeaker(speaker_label=label, start_ts=start, end_ts=end)


class TestMaxOverlapTurn:
    def test_no_turns_returns_none(self):
        assert max_overlap_turn(0.0, 5.0, []) is None

    def test_no_overlap_returns_none(self):
        # Utterance falls entirely between two turns.
        turns = [_turn(0.0, 1.0), _turn(10.0, 12.0)]
        assert max_overlap_turn(5.0, 6.0, turns) is None

    def test_full_containment_picks_containing_turn(self):
        turns = [_turn(0.0, 5.0, "A"), _turn(5.0, 10.0, "B")]
        result = max_overlap_turn(2.0, 4.0, turns)
        assert result is not None
        assert result.speaker_label == "A"

    def test_partial_overlap_picks_larger_overlap(self):
        # Utterance 4-7 overlaps A by 1s and B by 2s — B wins.
        turns = [_turn(0.0, 5.0, "A"), _turn(5.0, 10.0, "B")]
        result = max_overlap_turn(4.0, 7.0, turns)
        assert result is not None
        assert result.speaker_label == "B"

    def test_exactly_equal_overlap_picks_first(self):
        # When two turns tie, the linear scan keeps the earlier match —
        # tied overlap is not strictly greater than the running best.
        turns = [_turn(0.0, 5.0, "A"), _turn(5.0, 10.0, "B")]
        result = max_overlap_turn(3.0, 7.0, turns)  # 2s with A, 2s with B
        assert result is not None
        assert result.speaker_label == "A"

    def test_zero_overlap_at_boundary_returns_none(self):
        # Utterance ends exactly when turn starts — overlap is 0, not > 0,
        # so the helper returns None rather than picking arbitrarily.
        turns = [_turn(5.0, 10.0)]
        assert max_overlap_turn(0.0, 5.0, turns) is None

    def test_picks_best_among_many(self):
        turns = [
            _turn(0.0, 1.0, "A"),
            _turn(1.0, 2.0, "B"),
            _turn(2.0, 8.0, "C"),  # should win — biggest overlap with utt
            _turn(8.0, 9.0, "D"),
        ]
        result = max_overlap_turn(3.0, 7.0, turns)
        assert result is not None
        assert result.speaker_label == "C"


# ---------------------------------------------------------------------------
# Deepgram dict accessors
# ---------------------------------------------------------------------------


class TestUtterances:
    def test_present(self):
        resp = {"results": {"utterances": [{"start": 0.0, "transcript": "hi"}]}}
        assert utterances(resp) == [{"start": 0.0, "transcript": "hi"}]

    def test_missing_results_returns_empty(self):
        assert utterances({}) == []

    def test_missing_utterances_returns_empty(self):
        assert utterances({"results": {}}) == []

    def test_null_utterances_returns_empty(self):
        # Deepgram occasionally returns null instead of [] — the `or []`
        # fallback in the helper guards against this.
        assert utterances({"results": {"utterances": None}}) == []


class TestAudioDuration:
    def test_present(self):
        assert audio_duration({"metadata": {"duration": 123.45}}) == 123.45

    def test_missing_metadata(self):
        assert audio_duration({}) is None

    def test_missing_duration_field(self):
        assert audio_duration({"metadata": {}}) is None


class TestRequestId:
    def test_present(self):
        assert request_id({"metadata": {"request_id": "abc-123"}}) == "abc-123"

    def test_missing_metadata(self):
        assert request_id({}) is None

    def test_missing_request_id(self):
        assert request_id({"metadata": {}}) is None
