"""Unit tests for app.analyst.voice_clusters.aggregate_clusters.

Pure-function tests against ``TurnRow`` projections — no DB. The
``compute_voice_clusters`` wrapper that loads from SQLAlchemy is
covered by the integration tier (when added) since it touches DB +
pgvector.
"""

from uuid import UUID, uuid4

import pytest

from app.analyst.voice_clusters import (
    SAMPLE_TURN_LIMIT,
    TurnRow,
    aggregate_clusters,
)

PERSON_A = uuid4()
PERSON_B = uuid4()


def _turn(
    label: str,
    *,
    start: float = 0.0,
    end: float = 1.0,
    person: UUID | None = None,
    match_method: str | None = None,
    has_embedding: bool = True,
) -> TurnRow:
    return TurnRow(
        segment_id=uuid4(),
        speaker_label=label,
        start_ts=start,
        end_ts=end,
        speaker_person_id=person,
        match_method=match_method,
        has_embedding=has_embedding,
    )


class TestAggregateClusters:
    def test_empty_returns_empty(self):
        assert aggregate_clusters([]) == {"speakers": []}

    def test_groups_by_speaker_label(self):
        rows = [
            _turn("SPEAKER_00"),
            _turn("SPEAKER_00"),
            _turn("SPEAKER_01"),
        ]
        result = aggregate_clusters(rows)
        labels = [s["speaker_label"] for s in result["speakers"]]
        assert set(labels) == {"SPEAKER_00", "SPEAKER_01"}
        counts = {s["speaker_label"]: s["turn_count"] for s in result["speakers"]}
        assert counts == {"SPEAKER_00": 2, "SPEAKER_01": 1}

    def test_sorted_by_total_seconds_desc(self):
        rows = [
            _turn("SPEAKER_QUIET", start=0, end=5),       # 5 s
            _turn("SPEAKER_LOUD", start=0, end=100),      # 100 s
            _turn("SPEAKER_MID", start=0, end=20),        # 20 s
        ]
        result = aggregate_clusters(rows)
        labels = [s["speaker_label"] for s in result["speakers"]]
        assert labels == ["SPEAKER_LOUD", "SPEAKER_MID", "SPEAKER_QUIET"]

    def test_total_seconds_sums_per_label(self):
        rows = [
            _turn("SPEAKER_00", start=0, end=10),
            _turn("SPEAKER_00", start=20, end=25),
            _turn("SPEAKER_01", start=10, end=20),
        ]
        result = aggregate_clusters(rows)
        secs = {s["speaker_label"]: s["total_seconds"] for s in result["speakers"]}
        assert secs == {"SPEAKER_00": 15.0, "SPEAKER_01": 10.0}

    def test_dominant_person_is_mode(self):
        rows = [
            _turn("SPEAKER_00", person=PERSON_A),
            _turn("SPEAKER_00", person=PERSON_A),
            _turn("SPEAKER_00", person=PERSON_B),
            _turn("SPEAKER_00", person=None),  # unattributed turn doesn't vote
        ]
        result = aggregate_clusters(rows)
        sp = result["speakers"][0]
        assert sp["dominant_person_id"] == str(PERSON_A)
        # 2 votes for A out of 4 turn_count → 0.5 share.
        assert sp["dominant_share"] == 0.5

    def test_dominant_person_null_when_no_attribution(self):
        rows = [_turn("SPEAKER_00"), _turn("SPEAKER_00")]
        result = aggregate_clusters(rows)
        sp = result["speakers"][0]
        assert sp["dominant_person_id"] is None
        assert sp["dominant_share"] is None

    def test_match_method_breakdown_counts(self):
        rows = [
            _turn("SPEAKER_00", match_method="voice"),
            _turn("SPEAKER_00", match_method="voice+face"),
            _turn("SPEAKER_00", match_method=None),
            _turn("SPEAKER_00", match_method=None),
        ]
        result = aggregate_clusters(rows)
        sp = result["speakers"][0]
        assert sp["match_method_breakdown"] == {
            "voice": 1,
            "voice+face": 1,
            "null": 2,
        }

    def test_embedding_eligible_count_excludes_null_embedding_rows(self):
        rows = [
            _turn("SPEAKER_00", has_embedding=True),
            _turn("SPEAKER_00", has_embedding=False),  # sub-300ms turn
            _turn("SPEAKER_00", has_embedding=True),
        ]
        result = aggregate_clusters(rows)
        sp = result["speakers"][0]
        assert sp["turn_count"] == 3
        assert sp["embedding_eligible_count"] == 2

    def test_sample_turns_pick_longest_then_sorted_by_time(self):
        # Build a label with N>SAMPLE_TURN_LIMIT eligible turns of varied
        # durations + one ineligible (no embedding) turn that's the
        # longest of all. The ineligible one must be excluded from
        # samples.
        rows = [
            _turn("SPEAKER_00", start=10, end=15, has_embedding=True),   # 5
            _turn("SPEAKER_00", start=0, end=200, has_embedding=False),  # 200 ineligible
            _turn("SPEAKER_00", start=50, end=80, has_embedding=True),   # 30
            _turn("SPEAKER_00", start=100, end=110, has_embedding=True), # 10
            _turn("SPEAKER_00", start=300, end=320, has_embedding=True), # 20
            _turn("SPEAKER_00", start=400, end=415, has_embedding=True), # 15
            _turn("SPEAKER_00", start=500, end=502, has_embedding=True), # 2
            _turn("SPEAKER_00", start=600, end=640, has_embedding=True), # 40
        ]
        result = aggregate_clusters(rows)
        sp = result["speakers"][0]
        # Expect the 5 longest eligible durations [40, 30, 20, 15, 10],
        # then re-sorted by start_ts: [50, 100, 300, 400, 600].
        starts = [t["start_ts"] for t in sp["sample_turns"]]
        assert len(sp["sample_turns"]) == SAMPLE_TURN_LIMIT
        assert starts == [50.0, 100.0, 300.0, 400.0, 600.0]
        # And none of them is the ineligible 200-second turn.
        ineligible_start = 0.0
        assert ineligible_start not in starts

    def test_sample_turns_capped_at_limit(self):
        rows = [
            _turn("SPEAKER_00", start=i * 10, end=i * 10 + 5)
            for i in range(SAMPLE_TURN_LIMIT + 3)
        ]
        result = aggregate_clusters(rows)
        sp = result["speakers"][0]
        assert len(sp["sample_turns"]) == SAMPLE_TURN_LIMIT

    def test_preview_text_applied_by_segment(self):
        t1 = _turn("SPEAKER_00", start=0, end=10)
        t2 = _turn("SPEAKER_00", start=20, end=25)
        preview = {
            t1.segment_id: "Cleary is the top buy this week",
            t2.segment_id: "Yeah but you can't compare those two",
        }
        result = aggregate_clusters([t1, t2], preview)
        sp = result["speakers"][0]
        previews = {t["start_ts"]: t["preview_text"] for t in sp["sample_turns"]}
        assert previews[0.0] == "Cleary is the top buy this week"
        assert previews[20.0] == "Yeah but you can't compare those two"

    def test_preview_text_truncated_at_120_chars(self):
        t = _turn("SPEAKER_00", start=0, end=10)
        # 200-char text — should be truncated to <= 120 + '…'.
        text = "a " * 100
        result = aggregate_clusters([t], {t.segment_id: text})
        preview = result["speakers"][0]["sample_turns"][0]["preview_text"]
        # Cap is 120 + the ellipsis we append, never more.
        assert preview.endswith("…")
        assert len(preview) <= 121

    def test_preview_text_missing_defaults_to_empty_string(self):
        t = _turn("SPEAKER_00")
        result = aggregate_clusters([t], preview_by_segment={})
        assert result["speakers"][0]["sample_turns"][0]["preview_text"] == ""


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
