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
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from jeromelu_shared.db import SourceChunk, SourceDocument, SourceSpeaker

#: Sample turns surfaced per cluster for operator preview / click-to-listen.
#: Five is enough for the operator to confirm the voice without overflowing
#: the cluster header.
SAMPLE_TURN_LIMIT = 5

#: Cap on medoid voiceprints written per cluster assign. Mirrors
#: ``CLUSTER_EMBEDDING_SAMPLE_LIMIT=10`` on the face side — small enough
#: that one cluster-assign can't bloat the kNN registry, big enough to
#: capture acoustic variation across the cluster's timeline.
VOICEPRINT_SAMPLE_LIMIT = 10

#: Length cap for ``sample_turns[].preview_text``. Long enough to give the
#: operator context, short enough that five samples fit cleanly under the
#: cluster header.
_PREVIEW_TRUNCATE_AT = 120


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
                person_counts.items(), key=lambda kv: kv[1],
            )
            dominant_person_id = dom_pid
            dominant_share = dom_count / turn_count

        # Sample turns — longest with non-NULL embedding, then re-sorted
        # by start_ts so the operator sees them in conversational order.
        eligible = [t for t in turns if t.has_embedding]
        eligible.sort(key=lambda t: -(t.end_ts - t.start_ts))
        sampled = sorted(eligible[:SAMPLE_TURN_LIMIT], key=lambda t: t.start_ts)
        sample_turns = [
            {
                "segment_id": str(t.segment_id),
                "start_ts": float(t.start_ts),
                "end_ts": float(t.end_ts),
                "preview_text": _truncate(
                    preview_by_segment.get(t.segment_id, ""),
                ),
            }
            for t in sampled
        ]

        speakers.append({
            "speaker_label": label,
            "turn_count": turn_count,
            "total_seconds": float(total_seconds),
            "embedding_eligible_count": embedding_eligible,
            "dominant_person_id": dominant_person_id,
            "dominant_share": dominant_share,
            "match_method_breakdown": breakdown,
            "sample_turns": sample_turns,
        })

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
    """
    doc = (
        session.query(SourceDocument)
        .filter(SourceDocument.source_id == source_id)
        .first()
    )
    if not doc:
        return {"speakers": []}

    # Don't load ``embedding`` — it's a 256-dim pgvector we only need
    # to know is non-null. The boolean projection saves the pgvector
    # deserialisation cost across hundreds of rows.
    raw_rows = (
        session.query(
            SourceSpeaker.segment_id,
            SourceSpeaker.speaker_label,
            SourceSpeaker.start_ts,
            SourceSpeaker.end_ts,
            SourceSpeaker.speaker_person_id,
            SourceSpeaker.match_method,
            (SourceSpeaker.embedding.isnot(None)).label("has_embedding"),
        )
        .filter(SourceSpeaker.document_id == doc.document_id)
        .filter(SourceSpeaker.speaker_label.isnot(None))
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

    # Decide the per-cluster sample set up-front so the preview-text
    # fetch is one query across every sample turn, not one per cluster.
    sample_segment_ids: list[UUID] = []
    by_label: dict[str, list[TurnRow]] = {}
    for r in rows:
        by_label.setdefault(r.speaker_label, []).append(r)
    for turns in by_label.values():
        eligible = sorted(
            (t for t in turns if t.has_embedding),
            key=lambda t: -(t.end_ts - t.start_ts),
        )
        sample_segment_ids.extend(t.segment_id for t in eligible[:SAMPLE_TURN_LIMIT])

    preview_by_segment: dict[UUID, str] = {}
    if sample_segment_ids:
        chunk_rows = (
            session.query(
                SourceChunk.speaker_segment_id,
                SourceChunk.clean_text,
                SourceChunk.raw_text,
            )
            .filter(SourceChunk.speaker_segment_id.in_(sample_segment_ids))
            .order_by(SourceChunk.start_ts)
            .all()
        )
        # First chunk per segment wins — opening utterance usually
        # carries more identifying content than mid-turn filler.
        # ``clean_text`` is preferred but may be NULL on older rows.
        for seg_id, clean_text, raw_text in chunk_rows:
            if seg_id in preview_by_segment:
                continue
            text = (clean_text or raw_text or "").strip()
            preview_by_segment[seg_id] = text

    return aggregate_clusters(rows, preview_by_segment)


def _truncate(text: str) -> str:
    if len(text) <= _PREVIEW_TRUNCATE_AT:
        return text
    return text[:_PREVIEW_TRUNCATE_AT].rsplit(" ", 1)[0] + "…"
