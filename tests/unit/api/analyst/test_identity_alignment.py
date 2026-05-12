"""Unit tests for app.analyst.identity_alignment.compute_alignment.

Pure-function tests over ``DetectionRow`` and ``TurnRow`` projections —
no DB, no visual_id import chain. The ``fetch_alignment`` wrapper that
loads from SQLAlchemy is covered by the integration tier when added.
"""

from uuid import UUID, uuid4

import pytest

from app.analyst.identity_alignment import (
    DISAGREEMENT_LIMIT,
    MIN_ACTIVE_MOUTH_OPENING,
    MIN_OVERLAP_COUNT,
    ChunkRow,
    DetectionRow,
    TurnRow,
    compute_alignment,
)

PERSON_A = uuid4()
PERSON_B = uuid4()


def _det(
    ts: float,
    *,
    cluster: int | None = 0,
    mouth: float | None = 0.1,  # > MIN_ACTIVE_MOUTH_OPENING by default
    matched: UUID | None = None,
) -> DetectionRow:
    return DetectionRow(
        detection_id=uuid4(),
        frame_ts=ts,
        cluster_id=cluster,
        mouth_opening=mouth,
        matched_person_id=matched,
    )


def _turn(
    start: float,
    end: float,
    *,
    label: str | None = "SPEAKER_00",
    person: UUID | None = None,
    match_method: str | None = None,
) -> TurnRow:
    return TurnRow(
        segment_id=uuid4(),
        start_ts=start,
        end_ts=end,
        speaker_label=label,
        speaker_person_id=person,
        match_method=match_method,
    )


class TestCompute:
    def test_empty_inputs_produce_empty_payload(self):
        result = compute_alignment([], [])
        assert result == {
            "face_clusters": [],
            "voice_clusters": [],
            "alignment": [],
            "dominant_pairings": [],
            "disagreements": [],
            "timeline": [],
            "face_transcript": [],
            "conflated_turn_ids": [],
        }

    def test_face_clusters_sorted_by_detection_count_desc(self):
        dets = (
            [_det(float(i), cluster=0) for i in range(20)]
            + [_det(float(i), cluster=1) for i in range(50)]
            + [_det(float(i), cluster=2) for i in range(10)]
        )
        result = compute_alignment(dets, [])
        order = [c["cluster_id"] for c in result["face_clusters"]]
        assert order == [1, 0, 2]

    def test_voice_clusters_sorted_by_total_seconds_desc(self):
        turns = [
            _turn(0, 10, label="SPEAKER_00"),
            _turn(10, 100, label="SPEAKER_01"),
            _turn(100, 130, label="SPEAKER_02"),
        ]
        result = compute_alignment([], turns)
        order = [v["speaker_label"] for v in result["voice_clusters"]]
        assert order == ["SPEAKER_01", "SPEAKER_02", "SPEAKER_00"]

    def test_null_cluster_excluded_from_face_clusters(self):
        dets = [
            _det(float(i), cluster=0) for i in range(10)
        ] + [_det(99.0, cluster=None) for _ in range(20)]
        result = compute_alignment(dets, [])
        cluster_ids = {c["cluster_id"] for c in result["face_clusters"]}
        assert cluster_ids == {0}

    def test_null_label_excluded_from_voice_clusters(self):
        turns = [
            _turn(0, 10, label=None),  # NULL diariser output
            _turn(10, 20, label="SPEAKER_00"),
        ]
        result = compute_alignment([], turns)
        labels = {v["speaker_label"] for v in result["voice_clusters"]}
        assert labels == {"SPEAKER_00"}

    def test_overlap_count_matches_frames_inside_turns(self):
        # 30 frames inside SPEAKER_00's turn (0..30s), 10 outside.
        dets = (
            [_det(float(i), cluster=0) for i in range(30)]
            + [_det(float(i), cluster=0) for i in range(40, 50)]
        )
        turns = [
            _turn(0, 30, label="SPEAKER_00"),
        ]
        result = compute_alignment(dets, turns)
        # Only the 30 in-turn frames produce an alignment row.
        rows = result["alignment"]
        assert len(rows) == 1
        assert rows[0]["face_cluster_id"] == 0
        assert rows[0]["speaker_label"] == "SPEAKER_00"
        assert rows[0]["overlap_count"] == 30

    def test_active_overlap_count_filters_by_mouth_opening(self):
        # All 30 detections inside the turn; half above the active threshold,
        # half below.
        active_val = MIN_ACTIVE_MOUTH_OPENING + 0.01
        passive_val = MIN_ACTIVE_MOUTH_OPENING - 0.01
        dets = [
            _det(float(i), cluster=0, mouth=active_val) for i in range(15)
        ] + [
            _det(float(i), cluster=0, mouth=passive_val) for i in range(15, 30)
        ]
        turns = [_turn(0, 30, label="SPEAKER_00")]
        rows = compute_alignment(dets, turns)["alignment"]
        assert rows[0]["overlap_count"] == 30
        assert rows[0]["active_overlap_count"] == 15

    def test_low_overlap_pairs_filtered(self):
        # Under MIN_OVERLAP_COUNT detections in the pair — should drop.
        dets = [_det(float(i), cluster=0) for i in range(MIN_OVERLAP_COUNT - 1)]
        turns = [_turn(0, 100, label="SPEAKER_00")]
        rows = compute_alignment(dets, turns)["alignment"]
        assert rows == []

    def test_face_and_voice_shares_computed_correctly(self):
        # 30 frames in (cluster 0, SPEAKER_00), 70 in (cluster 0, SPEAKER_01).
        # Turns are non-overlapping with a small gap so the boundary
        # frame isn't ambiguous (both turn endpoints are inclusive — see
        # the interval walk in compute_alignment).
        dets = (
            [_det(float(i), cluster=0) for i in range(30)]   # 0..29 → SPEAKER_00
            + [_det(float(40 + i), cluster=0) for i in range(70)]  # 40..109 → SPEAKER_01
        )
        turns = [
            _turn(0, 29.5, label="SPEAKER_00"),     # ≈ 30 s
            _turn(39.5, 110, label="SPEAKER_01"),   # ≈ 70 s
        ]
        result = compute_alignment(dets, turns)
        by_label = {r["speaker_label"]: r for r in result["alignment"]}
        # Face cluster 0 has 100 detections total. 30 fell in SPEAKER_00.
        assert by_label["SPEAKER_00"]["face_cluster_share"] == pytest.approx(0.30)
        # SPEAKER_00 has ~29.5 s of turn total; 30 detections overlap → ~1.0
        # (at 1 fps detection-count ≈ seconds — see module docstring).
        assert by_label["SPEAKER_00"]["voice_cluster_share"] == pytest.approx(
            30 / 29.5,
        )
        # min(0.30, ~1.02) == 0.30 — confidence is the limiting modality.
        assert by_label["SPEAKER_00"]["confidence"] == pytest.approx(0.30)

    def test_dominant_pairings_greedy_one_to_one(self):
        # Build two distinct face clusters each overlapping primarily with
        # their own voice cluster, with a small bleed across.
        dets = (
            # Cluster 0 in SPEAKER_00 (heavy)
            [_det(float(i), cluster=0) for i in range(40)]
            # Cluster 0 also has 6 frames in SPEAKER_01 (low)
            + [_det(float(60 + i), cluster=0) for i in range(6)]
            # Cluster 1 in SPEAKER_01 (heavy)
            + [_det(float(60 + i), cluster=1) for i in range(30)]
            # Cluster 1 also has 6 frames in SPEAKER_00 (low)
            + [_det(float(i), cluster=1) for i in range(6)]
        )
        turns = [
            _turn(0, 40, label="SPEAKER_00"),
            _turn(60, 100, label="SPEAKER_01"),
        ]
        pairings = compute_alignment(dets, turns)["dominant_pairings"]
        # Both should be paired, 1:1.
        as_pairs = {(p["face_cluster_id"], p["speaker_label"]) for p in pairings}
        assert as_pairs == {(0, "SPEAKER_00"), (1, "SPEAKER_01")}

    def test_dominant_pairings_each_cluster_claimed_once(self):
        # If cluster 0 is the best match for both SPEAKER_00 and SPEAKER_01,
        # only the first pair wins; cluster 0 doesn't claim both voices.
        dets = (
            [_det(float(i), cluster=0) for i in range(40)]    # in SPEAKER_00
            + [_det(float(60 + i), cluster=0) for i in range(40)]  # in SPEAKER_01
        )
        turns = [
            _turn(0, 40, label="SPEAKER_00"),
            _turn(60, 100, label="SPEAKER_01"),
        ]
        pairings = compute_alignment(dets, turns)["dominant_pairings"]
        face_ids = [p["face_cluster_id"] for p in pairings]
        # Cluster 0 is greedy-claimed exactly once.
        assert face_ids.count(0) == 1

    def test_disagreement_flagged_when_face_and_voice_persons_differ(self):
        # SPEAKER_00 attributed to Person A via voice.
        # Cluster 0 dominantly matched to Person B via detections.
        # All cluster-0 detections fall in the SPEAKER_00 turn.
        # → expect one disagreement.
        dets = [
            _det(float(i), cluster=0, matched=PERSON_B) for i in range(30)
        ]
        turns = [_turn(0, 30, label="SPEAKER_00", person=PERSON_A)]
        result = compute_alignment(dets, turns)
        assert len(result["disagreements"]) == 1
        dis = result["disagreements"][0]
        assert dis["speaker_person_id"] == str(PERSON_A)
        assert dis["face_person_id"] == str(PERSON_B)
        assert dis["face_cluster_id"] == 0
        assert dis["speaker_label"] == "SPEAKER_00"

    def test_no_disagreement_when_persons_agree(self):
        dets = [_det(float(i), cluster=0, matched=PERSON_A) for i in range(30)]
        turns = [_turn(0, 30, label="SPEAKER_00", person=PERSON_A)]
        assert compute_alignment(dets, turns)["disagreements"] == []

    def test_no_disagreement_when_turn_has_no_attribution(self):
        # speaker_person_id NULL → can't disagree.
        dets = [_det(float(i), cluster=0, matched=PERSON_A) for i in range(30)]
        turns = [_turn(0, 30, label="SPEAKER_00", person=None)]
        assert compute_alignment(dets, turns)["disagreements"] == []

    def test_no_disagreement_when_face_cluster_has_no_dominant_person(self):
        # No detections matched → cluster has no dominant_person.
        dets = [_det(float(i), cluster=0, matched=None) for i in range(30)]
        turns = [_turn(0, 30, label="SPEAKER_00", person=PERSON_A)]
        assert compute_alignment(dets, turns)["disagreements"] == []

    def test_disagreements_sorted_by_duration_desc(self):
        # Three disagreements of different durations — longest first.
        dets = (
            [_det(float(i), cluster=0, matched=PERSON_B) for i in range(20)]
            + [_det(float(50 + i), cluster=0, matched=PERSON_B) for i in range(40)]
            + [_det(float(200 + i), cluster=0, matched=PERSON_B) for i in range(80)]
        )
        turns = [
            _turn(0, 20, label="SPEAKER_00", person=PERSON_A),
            _turn(50, 90, label="SPEAKER_01", person=PERSON_A),
            _turn(200, 280, label="SPEAKER_02", person=PERSON_A),
        ]
        labels = [
            d["speaker_label"]
            for d in compute_alignment(dets, turns)["disagreements"]
        ]
        # 80 s > 40 s > 20 s
        assert labels == ["SPEAKER_02", "SPEAKER_01", "SPEAKER_00"]

    def test_disagreements_capped_at_limit(self):
        # Build > DISAGREEMENT_LIMIT mismatched turns.
        # Each turn is 1 second wide, no overlap, separate cluster context.
        dets = []
        turns = []
        n = DISAGREEMENT_LIMIT + 10
        # Cluster 0 dominated by PERSON_B (one large mass of frames).
        # Each tiny turn has matching-cluster frames placed inside it.
        for i in range(n):
            start = float(i * 2)  # turns at 0, 2, 4, ...
            # Place MIN_OVERLAP_COUNT detections in each, all in cluster 0
            # matched to PERSON_B.
            dets.extend(
                _det(start + j * 0.1, cluster=0, matched=PERSON_B)
                for j in range(MIN_OVERLAP_COUNT)
            )
            turns.append(_turn(start, start + 1.0, label=f"SPEAKER_{i:02d}", person=PERSON_A))
        result = compute_alignment(dets, turns)
        assert len(result["disagreements"]) == DISAGREEMENT_LIMIT


class TestTimeline:
    def test_timeline_chronological_one_row_per_turn(self):
        # Out-of-order input; timeline must be sorted by start_ts asc.
        turns = [
            _turn(200, 210, label="SPEAKER_01"),
            _turn(0, 10, label="SPEAKER_00"),
            _turn(100, 130, label="SPEAKER_00"),
        ]
        result = compute_alignment([], turns)
        starts = [t["start_ts"] for t in result["timeline"]]
        assert starts == [0.0, 100.0, 200.0]

    def test_timeline_excludes_null_speaker_label(self):
        # Turns without a pyannote label can't participate in voice
        # clustering — leave them off the timeline.
        turns = [
            _turn(0, 10, label="SPEAKER_00"),
            _turn(20, 30, label=None),
        ]
        result = compute_alignment([], turns)
        assert len(result["timeline"]) == 1
        assert result["timeline"][0]["speaker_label"] == "SPEAKER_00"

    def test_timeline_row_carries_required_fields(self):
        t = _turn(
            10.5, 14.2, label="SPEAKER_00",
            person=PERSON_A, match_method="voice+face",
        )
        # Add per-modality + confidence fields the wrapper would fill.
        t = TurnRow(
            segment_id=t.segment_id,
            start_ts=t.start_ts,
            end_ts=t.end_ts,
            speaker_label=t.speaker_label,
            speaker_person_id=t.speaker_person_id,
            match_method=t.match_method,
            audio_match_person_id=PERSON_A,
            visual_match_person_id=PERSON_A,
            match_confidence=0.91,
        )
        preview = {t.segment_id: "Some words spoken"}
        result = compute_alignment([], [t], preview_by_segment=preview)
        row = result["timeline"][0]
        assert row["segment_id"] == str(t.segment_id)
        assert row["start_ts"] == 10.5
        assert row["end_ts"] == 14.2
        assert row["duration"] == pytest.approx(3.7)
        assert row["speaker_label"] == "SPEAKER_00"
        assert row["speaker_person_id"] == str(PERSON_A)
        assert row["match_method"] == "voice+face"
        assert row["match_confidence"] == 0.91
        assert row["audio_match_person_id"] == str(PERSON_A)
        assert row["visual_match_person_id"] == str(PERSON_A)
        assert row["preview_text"] == "Some words spoken"

    def test_timeline_agreement_agree(self):
        # Voice cluster dominated by PERSON_A; face cluster dominated by A.
        dets = [_det(float(i), cluster=0, matched=PERSON_A) for i in range(10)]
        turns = [_turn(0, 10, label="SPEAKER_00", person=PERSON_A)]
        row = compute_alignment(dets, turns)["timeline"][0]
        assert row["voice_cluster_person_id"] == str(PERSON_A)
        assert row["face_cluster_person_id"] == str(PERSON_A)
        assert row["agreement"] == "agree"
        assert row["face_cluster_id"] == 0

    def test_timeline_agreement_disagree(self):
        # Voice cluster says A; face cluster says B.
        dets = [_det(float(i), cluster=0, matched=PERSON_B) for i in range(10)]
        turns = [_turn(0, 10, label="SPEAKER_00", person=PERSON_A)]
        row = compute_alignment(dets, turns)["timeline"][0]
        assert row["voice_cluster_person_id"] == str(PERSON_A)
        assert row["face_cluster_person_id"] == str(PERSON_B)
        assert row["agreement"] == "disagree"

    def test_timeline_agreement_partial_voice_only(self):
        # Voice attributed to A; no face detections in the turn.
        turns = [_turn(0, 10, label="SPEAKER_00", person=PERSON_A)]
        row = compute_alignment([], turns)["timeline"][0]
        assert row["voice_cluster_person_id"] == str(PERSON_A)
        assert row["face_cluster_person_id"] is None
        assert row["face_cluster_id"] is None
        assert row["agreement"] == "partial"

    def test_timeline_agreement_partial_face_only(self):
        # Face cluster dominated by A; voice cluster has no attribution.
        dets = [_det(float(i), cluster=0, matched=PERSON_A) for i in range(10)]
        turns = [_turn(0, 10, label="SPEAKER_00", person=None)]
        row = compute_alignment(dets, turns)["timeline"][0]
        assert row["voice_cluster_person_id"] is None
        assert row["face_cluster_person_id"] == str(PERSON_A)
        assert row["agreement"] == "partial"

    def test_timeline_agreement_none(self):
        # Turn unattributed and no face detections.
        turns = [_turn(0, 10, label="SPEAKER_00", person=None)]
        row = compute_alignment([], turns)["timeline"][0]
        assert row["agreement"] == "none"

    def test_timeline_face_counts_per_turn(self):
        active_val = 0.06  # above MIN_ACTIVE_MOUTH_OPENING=0.045
        passive_val = 0.02  # below
        dets = (
            [_det(float(i), cluster=0, mouth=active_val) for i in range(7)]
            + [_det(float(i), cluster=0, mouth=passive_val) for i in range(7, 10)]
        )
        turns = [_turn(0, 10, label="SPEAKER_00")]
        row = compute_alignment(dets, turns)["timeline"][0]
        assert row["total_face_count"] == 10
        assert row["active_face_count"] == 7

    def test_timeline_face_cluster_is_dominant_in_turn(self):
        # Two clusters overlap with the turn; the one with more frames
        # is the dominant face cluster for that timeline row.
        dets = (
            [_det(float(i), cluster=1) for i in range(2)]
            + [_det(float(i + 3), cluster=0) for i in range(7)]
        )
        turns = [_turn(0, 10, label="SPEAKER_00")]
        row = compute_alignment(dets, turns)["timeline"][0]
        # Cluster 0 had 7 frames, cluster 1 had 2 — dominant is 0.
        assert row["face_cluster_id"] == 0


def _chunk(start: float, end: float, text: str = "hello world") -> ChunkRow:
    return ChunkRow(
        chunk_id=uuid4(),
        start_ts=start,
        end_ts=end,
        text=text,
    )


class TestFaceTranscript:
    def test_empty_chunks_yields_empty(self):
        result = compute_alignment([], [], chunks=[])
        assert result["face_transcript"] == []
        assert result["conflated_turn_ids"] == []

    def test_chunks_without_overlapping_detections_have_null_cluster(self):
        # Chunk has no detections in its window → cluster_id stays None.
        chunks = [_chunk(0, 5, "alone")]
        result = compute_alignment([], [], chunks=chunks)
        runs = result["face_transcript"]
        assert len(runs) == 1
        assert runs[0]["face_cluster_id"] is None
        assert runs[0]["text"] == "alone"

    def test_consecutive_same_cluster_chunks_merged_into_one_run(self):
        # Three chunks all with cluster 0 → one face_run.
        chunks = [
            _chunk(0, 5, "one"),
            _chunk(5, 10, "two"),
            _chunk(10, 15, "three"),
        ]
        # Detections placing cluster 0 inside each chunk window.
        dets = [
            _det(float(i), cluster=0)
            for i in range(15)
        ]
        result = compute_alignment(dets, [], chunks=chunks)
        runs = result["face_transcript"]
        assert len(runs) == 1
        assert runs[0]["face_cluster_id"] == 0
        assert runs[0]["text"] == "one two three"
        assert runs[0]["chunk_count"] == 3

    def test_face_cluster_change_starts_new_run(self):
        # Two chunks under cluster 0, two under cluster 1 → two runs.
        chunks = [
            _chunk(0, 5, "denan A"),
            _chunk(5, 10, "denan B"),
            _chunk(10, 15, "tyson A"),
            _chunk(15, 20, "tyson B"),
        ]
        dets = (
            [_det(float(i), cluster=0) for i in range(10)]
            + [_det(float(i + 10), cluster=1) for i in range(10)]
        )
        result = compute_alignment(dets, [], chunks=chunks)
        runs = result["face_transcript"]
        assert len(runs) == 2
        assert runs[0]["face_cluster_id"] == 0
        assert runs[0]["text"] == "denan A denan B"
        assert runs[1]["face_cluster_id"] == 1
        assert runs[1]["text"] == "tyson A tyson B"

    def test_conflated_turn_id_when_two_face_runs_inside_one_pyannote_turn(self):
        # One pyannote turn spans 0..20s.
        # Inside it: cluster 0 chunks 0..10, then cluster 1 chunks 10..20.
        # Two face runs → pyannote turn is conflated.
        chunks = [
            _chunk(0, 10, "denan"),
            _chunk(10, 20, "tyson"),
        ]
        dets = (
            [_det(float(i), cluster=0) for i in range(10)]
            + [_det(float(i + 10), cluster=1) for i in range(10)]
        )
        turn = _turn(0, 20, label="SPEAKER_00")
        result = compute_alignment(dets, [turn], chunks=chunks)
        assert result["conflated_turn_ids"] == [str(turn.segment_id)]

    def test_no_conflation_when_face_runs_match_one_pyannote_turn_each(self):
        # Pyannote made two turns at the face boundary — no conflation.
        chunks = [
            _chunk(0, 10, "denan"),
            _chunk(10, 20, "tyson"),
        ]
        dets = (
            [_det(float(i), cluster=0) for i in range(10)]
            + [_det(float(i + 10), cluster=1) for i in range(10)]
        )
        turns = [
            _turn(0, 10, label="SPEAKER_00"),
            _turn(10, 20, label="SPEAKER_01"),
        ]
        result = compute_alignment(dets, turns, chunks=chunks)
        assert result["conflated_turn_ids"] == []

    def test_no_face_run_does_not_conflate_a_turn(self):
        # A turn with one face-cluster run and one no-face run shouldn't
        # be conflated — silence/off-screen is not a speaker change.
        chunks = [
            _chunk(0, 10, "denan"),
            _chunk(10, 20, "still denan, but the camera cut away"),
        ]
        dets = [_det(float(i), cluster=0) for i in range(10)]  # only first chunk
        turn = _turn(0, 20, label="SPEAKER_00")
        result = compute_alignment(dets, [turn], chunks=chunks)
        # Two face_runs (cluster=0 then cluster=None), but None doesn't
        # count toward conflation.
        assert result["conflated_turn_ids"] == []

    def test_face_run_pyannote_turn_ids_lists_overlapping_turns(self):
        # One face run spans 0..20s and overlaps two pyannote turns.
        chunks = [_chunk(0, 10, "a"), _chunk(10, 20, "b")]
        dets = [_det(float(i), cluster=0) for i in range(20)]
        turn_a = _turn(0, 10, label="SPEAKER_00")
        turn_b = _turn(10, 20, label="SPEAKER_01")
        result = compute_alignment(dets, [turn_a, turn_b], chunks=chunks)
        run = result["face_transcript"][0]
        ids = set(run["pyannote_turn_ids"])
        assert ids == {str(turn_a.segment_id), str(turn_b.segment_id)}

    def test_dominant_cluster_tie_broken_by_cluster_id_asc(self):
        # 2 frames each from cluster 0 and 1 in a single chunk — ties
        # break on cluster_id ascending for determinism.
        chunks = [_chunk(0, 5, "tied")]
        dets = [
            _det(1.0, cluster=1),
            _det(2.0, cluster=0),
            _det(3.0, cluster=1),
            _det(4.0, cluster=0),
        ]
        run = compute_alignment(dets, [], chunks=chunks)["face_transcript"][0]
        assert run["face_cluster_id"] == 0


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
