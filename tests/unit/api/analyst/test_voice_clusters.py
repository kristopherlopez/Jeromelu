"""Unit tests for app.analyst.voice_clusters.aggregate_clusters.

Pure-function tests against ``TurnRow`` projections — no DB. The
``compute_voice_clusters`` wrapper that loads from SQLAlchemy is
covered by the integration tier (when added) since it touches DB +
pgvector.
"""

from uuid import UUID, uuid4

import pytest

from app.analyst.voice_clusters import TurnRow, aggregate_clusters

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

    def test_first_and_last_ts_on_cluster(self):
        # first_ts = earliest start; last_ts = latest end. Both span the
        # entire cluster's appearance, not just one turn.
        rows = [
            _turn("SPEAKER_00", start=300, end=350),
            _turn("SPEAKER_00", start=100, end=120),
            _turn("SPEAKER_00", start=500, end=540),
        ]
        result = aggregate_clusters(rows)
        sp = result["speakers"][0]
        assert sp["first_ts"] == 100.0
        assert sp["last_ts"] == 540.0

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

    def test_turns_returned_in_chronological_order(self):
        # Insertion order is arbitrary; turns array must be sorted by
        # start_ts so the operator reads the conversation top-to-bottom.
        rows = [
            _turn("SPEAKER_00", start=300, end=305),
            _turn("SPEAKER_00", start=100, end=110),
            _turn("SPEAKER_00", start=200, end=215),
            _turn("SPEAKER_00", start=50, end=55),
        ]
        result = aggregate_clusters(rows)
        starts = [t["start_ts"] for t in result["speakers"][0]["turns"]]
        assert starts == [50.0, 100.0, 200.0, 300.0]

    def test_turns_contains_every_turn_not_a_sample(self):
        # Comprehensive view: every turn in the cluster must appear.
        # The previous 5-sample preview behaviour is gone.
        rows = [_turn("SPEAKER_00", start=i * 10, end=i * 10 + 5)
                for i in range(20)]
        result = aggregate_clusters(rows)
        assert len(result["speakers"][0]["turns"]) == 20

    def test_turn_row_shape_carries_all_review_fields(self):
        t = _turn(
            "SPEAKER_00",
            start=10.5,
            end=14.2,
            person=PERSON_A,
            match_method="voice+face",
            has_embedding=True,
        )
        preview = {t.segment_id: "Some words spoken"}
        result = aggregate_clusters([t], preview)
        row = result["speakers"][0]["turns"][0]
        assert row["segment_id"] == str(t.segment_id)
        assert row["start_ts"] == 10.5
        assert row["end_ts"] == 14.2
        assert row["duration"] == pytest.approx(3.7)
        assert row["speaker_person_id"] == str(PERSON_A)
        assert row["match_method"] == "voice+face"
        assert row["has_embedding"] is True
        assert row["preview_text"] == "Some words spoken"

    def test_preview_text_applied_by_segment(self):
        t1 = _turn("SPEAKER_00", start=0, end=10)
        t2 = _turn("SPEAKER_00", start=20, end=25)
        preview = {
            t1.segment_id: "Cleary is the top buy this week",
            t2.segment_id: "Yeah but you can't compare those two",
        }
        result = aggregate_clusters([t1, t2], preview)
        sp = result["speakers"][0]
        previews = {t["start_ts"]: t["preview_text"] for t in sp["turns"]}
        assert previews[0.0] == "Cleary is the top buy this week"
        assert previews[20.0] == "Yeah but you can't compare those two"

    def test_preview_text_truncated_on_long_input(self):
        t = _turn("SPEAKER_00", start=0, end=10)
        # 600-char text — should be truncated to ~300 chars with a soft
        # word-boundary break + ellipsis.
        text = ("a " * 300).strip()
        result = aggregate_clusters([t], {t.segment_id: text})
        preview = result["speakers"][0]["turns"][0]["preview_text"]
        assert preview.endswith("…")
        # Truncated to the cap with at most a few extra chars from the
        # ellipsis. 310 is conservative headroom.
        assert len(preview) <= 310

    def test_preview_text_short_input_passes_through(self):
        t = _turn("SPEAKER_00", start=0, end=10)
        result = aggregate_clusters([t], {t.segment_id: "Short and clean"})
        preview = result["speakers"][0]["turns"][0]["preview_text"]
        assert preview == "Short and clean"

    def test_preview_text_missing_defaults_to_empty_string(self):
        t = _turn("SPEAKER_00")
        result = aggregate_clusters([t], preview_by_segment={})
        assert result["speakers"][0]["turns"][0]["preview_text"] == ""


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
