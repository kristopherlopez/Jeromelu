"""Voice-cluster aggregation over ``source_speakers`` for the Voices tab.

Unlike face clusters (which need an HDBSCAN pass over per-detection
ArcFace embeddings — see ``face_clusters.py``), voice clusters are
pre-computed for free at diarisation time: pyannote tags every turn
with a ``SPEAKER_NN`` label that's already a per-source clustering.
The Voices tab is therefore pure aggregation — no clustering step, no
embedding-matrix load, just a group-by over ``source_speakers.speaker_label``.

Mirrors the per-cluster shape produced by
``face_runs.compute_face_runs_from_detections`` so the frontend can
reuse the same per-cluster layout and bulk-assign modal contract.
Each cluster exposes *every* turn (not just a 5-sample preview) so the
review surface is as comprehensive as the Faces tab's runs view.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from jeromelu_shared.db import SourceChunk, SourceDocument, SourceSpeaker
from sqlalchemy import func
from sqlalchemy.orm import Session

#: Cap on medoid voiceprints written per cluster assign. Mirrors
#: ``CLUSTER_EMBEDDING_SAMPLE_LIMIT=10`` on the face side — small enough
#: that one cluster-assign can't bloat the kNN registry, big enough to
#: capture acoustic variation across the cluster's timeline.
VOICEPRINT_SAMPLE_LIMIT = 10


@dataclass(frozen=True)
class TurnRow:
    """Minimal turn projection consumed by :func:`aggregate_clusters`.

    Kept as a tiny dataclass rather than the full ``SourceSpeaker`` ORM
    object so the aggregation helper is trivially unit-testable without
    a DB session — the DB wrapper builds these from query results.
    """

    segment_id: UUID
    speaker_label: str
    start_ts: float
    end_ts: float
    speaker_person_id: UUID | None
    match_method: str | None
    has_embedding: bool


def aggregate_clusters(
    rows: list[TurnRow],
    preview_by_segment: dict[UUID, str] | None = None,
) -> dict:
    """Pure aggregation over a list of :class:`TurnRow` projections.

    Returns one entry per ``speaker_label`` ordered by total airtime
    descending. Rows with a NULL ``speaker_label`` must be filtered out
    by the caller — they don't belong to any cluster.

    Each cluster's ``turns`` list contains *every* turn in the cluster,
    sorted chronologically by ``start_ts``. Each turn carries its
    time range, duration, current attribution, match_method, and the
    concatenated chunk text covered by that turn.
    """
    preview_by_segment = preview_by_segment or {}

    by_label: dict[str, list[TurnRow]] = {}
    for r in rows:
        by_label.setdefault(r.speaker_label, []).append(r)

    speakers = []
    for label, turns in by_label.items():
        turn_count = len(turns)
        total_seconds = sum(t.end_ts - t.start_ts for t in turns)
        embedding_eligible = sum(1 for t in turns if t.has_embedding)
        first_ts = min(t.start_ts for t in turns)
        last_ts = max(t.end_ts for t in turns)

        breakdown: dict[str, int] = {}
        for t in turns:
            key = t.match_method or "null"
            breakdown[key] = breakdown.get(key, 0) + 1

        person_counts: dict[str, int] = {}
        for t in turns:
            if t.speaker_person_id:
                pid = str(t.speaker_person_id)
                person_counts[pid] = person_counts.get(pid, 0) + 1
        dominant_person_id: str | None = None
        dominant_share: float | None = None
        if person_counts:
            dom_pid, dom_count = max(
                person_counts.items(),
                key=lambda kv: kv[1],
            )
            dominant_person_id = dom_pid
            dominant_share = dom_count / turn_count

        # Every turn in the cluster, sorted chronologically so the
        # operator scans the conversation in playback order. Symmetric
        # with the Faces tab's per-cluster run list. ``preview_text`` is
        # the full concatenated chunk text — no truncation — so the
        # operator can read what was actually said without clicking
        # through to the transcript tab.
        chrono_turns = sorted(turns, key=lambda t: t.start_ts)
        turns_out = [
            {
                "segment_id": str(t.segment_id),
                "start_ts": float(t.start_ts),
                "end_ts": float(t.end_ts),
                "duration": float(t.end_ts - t.start_ts),
                "speaker_person_id": (str(t.speaker_person_id) if t.speaker_person_id else None),
                "match_method": t.match_method,
                "has_embedding": t.has_embedding,
                "preview_text": preview_by_segment.get(t.segment_id, ""),
            }
            for t in chrono_turns
        ]

        speakers.append(
            {
                "speaker_label": label,
                "turn_count": turn_count,
                "total_seconds": float(total_seconds),
                "first_ts": float(first_ts),
                "last_ts": float(last_ts),
                "embedding_eligible_count": embedding_eligible,
                "dominant_person_id": dominant_person_id,
                "dominant_share": dominant_share,
                "match_method_breakdown": breakdown,
                "turns": turns_out,
            }
        )

    speakers.sort(key=lambda s: -s["total_seconds"])
    return {"speakers": speakers}


def compute_voice_clusters(session: Session, source_id: UUID) -> dict:
    """Aggregate ``source_speakers`` rows by ``speaker_label`` for one source.

    Thin DB wrapper around :func:`aggregate_clusters`. Returns one entry
    per pyannote speaker for this source, ordered by total airtime
    descending. Turns with NULL ``speaker_label`` are excluded — they
    don't belong to any cluster. Turns with NULL ``embedding`` are
    counted in the headline stats but flagged as ineligible for
    voiceprint enrolment (via ``embedding_eligible_count``) so the
    assign modal can warn when a cluster has nothing to write into
    ``person_voiceprints``.

    For every turn the wrapper concatenates the text of every
    ``source_chunks`` row that joins back to it — the full speech for
    the turn, not just the opening utterance — so the Voices tab can
    show what was said. One indexed query, regardless of cluster count.
    """
    doc = session.query(SourceDocument).filter(SourceDocument.source_id == source_id).first()
    if not doc:
        return {"speakers": []}

    # Don't load ``embedding`` — it's a 256-dim pgvector we only need
    # to know is non-null. The boolean projection saves the pgvector
    # deserialisation cost across hundreds of rows.
    #
    # Group by ``coalesce(cluster_label, speaker_label)`` so any custom
    # clustering pass (HDBSCAN over wespeaker medoids, manual edits,
    # face-driven re-segmentation) takes precedence over pyannote's raw
    # SPEAKER_NN. NULL ``cluster_label`` falls through to ``speaker_label``
    # so a partially-clustered source (HDBSCAN-noise turns) stays
    # navigable under its original pyannote grouping.
    effective_label = func.coalesce(
        SourceSpeaker.cluster_label,
        SourceSpeaker.speaker_label,
    ).label("speaker_label")
    raw_rows = (
        session.query(
            SourceSpeaker.segment_id,
            effective_label,
            SourceSpeaker.start_ts,
            SourceSpeaker.end_ts,
            SourceSpeaker.speaker_person_id,
            SourceSpeaker.match_method,
            (SourceSpeaker.embedding.isnot(None)).label("has_embedding"),
        )
        .filter(SourceSpeaker.document_id == doc.document_id)
        .filter(
            func.coalesce(
                SourceSpeaker.cluster_label,
                SourceSpeaker.speaker_label,
            ).isnot(None),
        )
        .order_by(SourceSpeaker.start_ts)
        .all()
    )

    rows = [
        TurnRow(
            segment_id=r.segment_id,
            speaker_label=r.speaker_label,
            start_ts=float(r.start_ts),
            end_ts=float(r.end_ts),
            speaker_person_id=r.speaker_person_id,
            match_method=r.match_method,
            has_embedding=bool(r.has_embedding),
        )
        for r in raw_rows
    ]

    spans = [(r.segment_id, r.start_ts, r.end_ts) for r in rows]
    preview_by_segment = fetch_full_turn_text(
        session,
        spans,
        document_id=doc.document_id,
    )

    return aggregate_clusters(rows, preview_by_segment)


def fetch_full_turn_text(
    session: Session,
    spans: list[tuple[UUID, float, float]],
    document_id: UUID,
) -> dict[UUID, str]:
    """Concatenate every ``source_chunks`` row that *overlaps in time* with
    each turn's ``[start_ts, end_ts]`` window.

    Why overlap, not FK lookup: pyannote turn boundaries are finer-grained
    than Deepgram utterance boundaries. The transcription merge assigns
    each utterance to one turn via ``source_chunks.speaker_segment_id``
    (max-overlap). With ~5× more pyannote turns than Deepgram utterances
    on typical podcasts, querying by FK leaves most turns with no text
    even though words *were* spoken during their window. Timestamp
    overlap surfaces every chunk that fell in the turn's window, so
    every turn shows what was said — at the cost that two adjacent turns
    sharing one long utterance both show the same sentence.

    Loads all chunks for the document in one query, then buckets in
    Python via :func:`bucket_chunks_to_spans`. The pure-Python step is
    unit-testable; the SQL load is trivial at podcast scale.
    """
    if not spans:
        return {}
    chunk_rows = (
        session.query(
            SourceChunk.start_ts,
            SourceChunk.end_ts,
            SourceChunk.clean_text,
            SourceChunk.raw_text,
        )
        .filter(SourceChunk.document_id == document_id)
        .filter(SourceChunk.start_ts.isnot(None))
        .filter(SourceChunk.end_ts.isnot(None))
        .order_by(SourceChunk.start_ts)
        .all()
    )
    chunks: list[tuple[float, float, str]] = []
    for start_ts, end_ts, clean_text, raw_text in chunk_rows:
        text = (clean_text or raw_text or "").strip()
        if not text:
            continue
        chunks.append((float(start_ts), float(end_ts), text))
    return bucket_chunks_to_spans(chunks, spans)


def bucket_chunks_to_spans(
    chunks: list[tuple[float, float, str]],
    spans: list[tuple[UUID, float, float]],
) -> dict[UUID, str]:
    """Pure-Python: bucket chunk texts into spans they overlap in time.

    Spans don't have to be sorted on input — the function sorts a copy
    internally so the inner loop can early-break once we've walked past
    a chunk's end. Output keys are every span's ``segment_id`` (even
    spans with zero overlapping chunks, which map to ``""``).

    A chunk is considered to overlap a span when
    ``chunk.start <= span.end AND chunk.end >= span.start`` — touching
    boundaries count, since pyannote turn boundaries and Deepgram
    utterance boundaries are independently estimated and often sit a
    fraction of a second apart.
    """
    out: dict[UUID, list[str]] = {seg_id: [] for seg_id, _s, _e in spans}
    spans_sorted = sorted(spans, key=lambda s: s[1])
    for chunk_start, chunk_end, text in chunks:
        for seg_id, span_start, span_end in spans_sorted:
            if span_end < chunk_start:
                continue
            if span_start > chunk_end:
                break
            out[seg_id].append(text)
    return {seg_id: " ".join(parts) for seg_id, parts in out.items()}
