import hashlib
import json
import uuid
from datetime import UTC, date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    pass


class Channel(Base):
    __tablename__ = "channels"

    channel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    quality_rating: Mapped[int] = mapped_column(Integer, default=5)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    logo_url: Mapped[str | None] = mapped_column(Text)
    handle: Mapped[str | None] = mapped_column(Text)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    sources: Mapped[list["Source"]] = relationship(back_populates="channel")

    __table_args__ = (
        CheckConstraint(
            "platform IN ('youtube', 'podcast', 'website', 'twitter', 'instagram')",
            name="ck_channel_platform",
        ),
        UniqueConstraint("platform", "external_id", name="uq_channel_platform_external"),
        Index("idx_channels_platform", "platform"),
        Index("idx_channels_active", "active"),
    )


class Source(Base):
    __tablename__ = "sources"

    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    channel_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channels.channel_id"))
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    is_short: Mapped[bool | None] = mapped_column(
        Boolean,
        Computed("duration_seconds IS NOT NULL AND duration_seconds < 60", persisted=True),
    )
    creator_name: Mapped[str | None] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(Text, unique=True)
    approved_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ingestion_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    transcription_status: Mapped[str | None] = mapped_column(Text)
    extraction_method: Mapped[str | None] = mapped_column(Text)
    diarization_method: Mapped[str | None] = mapped_column(Text)
    audio_s3_key: Mapped[str | None] = mapped_column(Text)
    video_s3_key: Mapped[str | None] = mapped_column(Text)
    video_format: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    channel: Mapped["Channel | None"] = relationship(back_populates="sources")
    documents: Mapped[list["SourceDocument"]] = relationship(back_populates="source", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("source_type IN ('youtube', 'podcast', 'web', 'radio', 'manual')", name="ck_source_type"),
        CheckConstraint(
            "extraction_method IS NULL OR extraction_method IN ("
            "'deepgram_v1', 'deepgram_words+pyannote_v1', 'youtube_captions')",
            name="ck_sources_extraction_method",
        ),
        CheckConstraint(
            "transcription_status IS NULL OR transcription_status IN ('transcribed', 'failed')",
            name="ck_sources_transcription_status",
        ),
        CheckConstraint(
            "video_format IS NULL OR video_format IN ('multi_cam', 'single_cam', 'audio_only')",
            name="ck_sources_video_format",
        ),
        Index("idx_sources_type", "source_type"),
        Index("idx_sources_approved", "approved_flag"),
    )


class SourceDocument(Base):
    __tablename__ = "source_documents"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.source_id"), nullable=False)
    s3_key: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    cleaned_text: Mapped[str | None] = mapped_column(Text)
    transcript_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    language: Mapped[str] = mapped_column(Text, default="en")
    checksum: Mapped[str | None] = mapped_column(Text)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    source: Mapped["Source"] = relationship(back_populates="documents")
    chunks: Mapped[list["SourceChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    quotes: Mapped[list["Quote"]] = relationship(back_populates="document")

    __table_args__ = (Index("idx_source_documents_source", "source_id"),)


class SourceChunk(Base):
    """Utterance-grained transcript chunk.

    After migration 044 (audio-first extract), chunks are produced one-per
    Deepgram utterance and link to a `SourceSpeaker` segment via
    `speaker_segment_id`. Column order mirrors the new schema:
    identifiers → time → space → text → semantic.
    """

    __tablename__ = "source_chunks"

    chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    speaker_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_speakers.segment_id", ondelete="SET NULL"),
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ts: Mapped[float | None] = mapped_column(Float)
    end_ts: Mapped[float | None] = mapped_column(Float)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    clean_text: Mapped[str | None] = mapped_column(Text)
    paragraph_break: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    embedding = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    document: Mapped["SourceDocument"] = relationship(back_populates="chunks")
    speaker_segment: Mapped["SourceSpeaker | None"] = relationship()
    claim_links: Mapped[list["ClaimChunk"]] = relationship(back_populates="chunk")

    __table_args__ = (
        CheckConstraint(
            "start_ts IS NULL OR end_ts IS NULL OR end_ts >= start_ts",
            name="ck_source_chunks_ts_span",
        ),
        UniqueConstraint("document_id", "chunk_index", name="uq_source_chunks_doc_index"),
        Index("idx_source_chunks_document", "document_id"),
        Index(
            "idx_source_chunks_speaker",
            "speaker_segment_id",
            postgresql_where="speaker_segment_id IS NOT NULL",
        ),
    )


class SourceSpeaker(Base):
    """Diarised speaker turn over a source document.

    Coarse-grained span layer above ``SourceChunk``. Populated by the
    diarisation pass (Deepgram or equivalent) after document ingest.
    ``speaker_person_id`` is NULL until the raw diariser label
    (``speaker_label``) is resolved to a known person. See migration 034.
    """

    __tablename__ = "source_speakers"

    segment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_documents.document_id", ondelete="CASCADE"), nullable=False
    )
    speaker_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.person_id", ondelete="SET NULL")
    )
    speaker_label: Mapped[str | None] = mapped_column(Text)
    cluster_label: Mapped[str | None] = mapped_column(Text)
    start_ts: Mapped[float] = mapped_column(Float, nullable=False)
    end_ts: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    embedding = mapped_column(Vector(256))
    embedding_model: Mapped[str | None] = mapped_column(Text)
    audio_match_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.person_id", ondelete="SET NULL"),
    )
    audio_match_score: Mapped[float | None] = mapped_column(Float)
    visual_match_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.person_id", ondelete="SET NULL"),
    )
    visual_match_score: Mapped[float | None] = mapped_column(Float)
    match_method: Mapped[str | None] = mapped_column(Text)
    match_confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        CheckConstraint("end_ts >= start_ts", name="ck_source_speakers_span"),
        CheckConstraint(
            "match_method IS NULL OR match_method IN ('voice', 'face', 'voice+face', 'manual')",
            name="ck_source_speakers_match_method",
        ),
        Index("idx_source_speakers_document", "document_id"),
        Index(
            "idx_source_speakers_person",
            "speaker_person_id",
            postgresql_where="speaker_person_id IS NOT NULL",
        ),
        Index("idx_source_speakers_doc_start", "document_id", "start_ts"),
        Index(
            "idx_source_speakers_audio_match",
            "audio_match_person_id",
            postgresql_where="audio_match_person_id IS NOT NULL",
        ),
        Index(
            "idx_source_speakers_visual_match",
            "visual_match_person_id",
            postgresql_where="visual_match_person_id IS NOT NULL",
        ),
    )


class PersonFaceEmbedding(Base):
    """Face fingerprint registry — Phase 4 visual identification.

    Sibling table to ``PersonVoiceprint``. Each row is one ArcFace
    embedding (512-dim, InsightFace `buffalo_l`) from a frame
    explicitly attributed to a Person. Multiple rows per Person let
    the registry capture visual variation (angles, lighting, age) and
    compound over time via Phase 5 cross-modal auto-confirmation.

    See migration 049.
    """

    __tablename__ = "person_face_embeddings"

    face_embedding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.person_id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.source_id", ondelete="SET NULL"),
    )
    frame_ts: Mapped[float | None] = mapped_column(Float)
    embedding = mapped_column(Vector(512), nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )

    __table_args__ = (
        CheckConstraint(
            "created_by IN ('manual', 'headshot', 'auto-confirmed')",
            name="ck_person_face_embeddings_created_by",
        ),
        Index("idx_person_face_embeddings_person", "person_id"),
        Index(
            "idx_person_face_embeddings_source",
            "source_id",
            postgresql_where="source_id IS NOT NULL",
        ),
    )


class SourceFaceDetection(Base):
    """Raw face-detection log per source — one row per detection during
    visual ID, embedding kept (instead of dropped into the face-track
    JSON). The face-track JSON is still the per-frame overlay cache;
    this table is the canonical embedding store for intra-source
    clustering and cross-source label propagation (Slice B).

    Separate from ``person_face_embeddings`` because that's the
    *registry* (one row per enrolled exemplar) while this is the
    *observation log* (one row per detection ≈ thousands per source).
    Different growth rates and lifecycles — the registry persists, the
    observation log is re-derivable from the source media.

    See migration 053.
    """

    __tablename__ = "source_face_detections"

    detection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.source_id", ondelete="CASCADE"),
        nullable=False,
    )
    frame_ts: Mapped[float] = mapped_column(Float, nullable=False)
    # bbox in source-frame pixel coords: [x1, y1, x2, y2]. Stored as
    # four columns so they're queryable; ck constraints enforce ordering.
    bbox_x1: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y1: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x2: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y2: Mapped[float] = mapped_column(Float, nullable=False)
    det_score: Mapped[float] = mapped_column(Float, nullable=False)
    embedding = mapped_column(Vector(512), nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    mouth_opening: Mapped[float | None] = mapped_column(Float)
    matched_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.person_id", ondelete="SET NULL"),
    )
    match_score: Mapped[float | None] = mapped_column(Float)
    # Populated by the per-source clustering pass (Slice B PR 2). NULL
    # = not yet clustered; expected initial state for fresh detections.
    cluster_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )

    __table_args__ = (
        CheckConstraint("bbox_x2 > bbox_x1", name="ck_source_face_detections_bbox_x"),
        CheckConstraint("bbox_y2 > bbox_y1", name="ck_source_face_detections_bbox_y"),
        Index("idx_source_face_detections_source_ts", "source_id", "frame_ts"),
        Index(
            "idx_source_face_detections_source_cluster",
            "source_id",
            "cluster_id",
            postgresql_where="cluster_id IS NOT NULL",
        ),
    )


class SourceFaceCluster(Base):
    """Per-cluster metadata for face clusters within a source.

    The detection-level table (mig 053) groups frames by ``cluster_id``;
    this table puts a first-class home around the cluster itself for the
    decisions an operator makes about it — kind (person / portrait /
    noise), an optional label override, exclusion from the default runs
    view, attributed person, and the diagnostic stats that informed the
    auto-tag heuristic.

    See migration 054.
    """

    __tablename__ = "source_face_clusters"

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.source_id", ondelete="CASCADE"),
        primary_key=True,
    )
    cluster_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str | None] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(Text)
    excluded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    detection_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mouth_open_std: Mapped[float | None] = mapped_column(Float)
    centroid_std: Mapped[float | None] = mapped_column(Float)
    temporal_density: Mapped[float | None] = mapped_column(Float)
    detected_kind: Mapped[str | None] = mapped_column(Text)
    attributed_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.person_id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )

    __table_args__ = (
        CheckConstraint(
            "kind IS NULL OR kind IN ('person', 'portrait', 'noise')",
            name="ck_source_face_clusters_kind",
        ),
        CheckConstraint(
            "detected_kind IS NULL OR detected_kind IN ('person', 'portrait', 'noise')",
            name="ck_source_face_clusters_detected_kind",
        ),
        Index("idx_source_face_clusters_source", "source_id"),
        Index(
            "idx_source_face_clusters_kind",
            "kind",
            postgresql_where="kind IS NOT NULL",
        ),
    )


class PersonVoiceprint(Base):
    """Voice fingerprint registry — Phase 3 of speaker identification.

    Each row is one sliding-window embedding (2 s window, 0.5 s hop)
    from a span of audio explicitly attributed to a Person. Multiple
    rows per enrollment session and multiple sessions per Person, so
    the registry compounds over time (Phase 5 cross-modal auto-confirm).

    See migration 048.
    """

    __tablename__ = "person_voiceprints"

    voiceprint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.person_id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.source_id", ondelete="SET NULL"),
    )
    start_ts: Mapped[float] = mapped_column(Float, nullable=False)
    end_ts: Mapped[float] = mapped_column(Float, nullable=False)
    embedding = mapped_column(Vector(256), nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )

    __table_args__ = (
        CheckConstraint("end_ts >= start_ts", name="ck_person_voiceprints_span"),
        CheckConstraint(
            "created_by IN ('manual', 'auto-confirmed')",
            name="ck_person_voiceprints_created_by",
        ),
        Index("idx_person_voiceprints_person", "person_id"),
        Index(
            "idx_person_voiceprints_source",
            "source_id",
            postgresql_where="source_id IS NOT NULL",
        ),
    )


class SourceChapter(Base):
    """Semantic chapter detected over a source document.

    Output of the analyse-transcript pipeline. Used to scope claim
    extraction (each chapter gets its own specialist agent) and to
    attribute claims back to a chapter for UI navigation. See migration 034.
    """

    __tablename__ = "source_chapters"

    chapter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_documents.document_id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    start_ts: Mapped[float] = mapped_column(Float, nullable=False)
    end_ts: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        CheckConstraint("end_ts >= start_ts", name="ck_source_chapters_span"),
        UniqueConstraint("document_id", "ordinal", name="uq_source_chapters_doc_ordinal"),
        Index("idx_source_chapters_document", "document_id"),
        Index("idx_source_chapters_doc_start", "document_id", "start_ts"),
    )


class Team(Base):
    """Canonical roster of every team across all grades feeding into NRL.

    Covers NRL, NRLW, and the male pathway feeders (NSW Cup, QLD Cup,
    Jersey Flegg, Mal Meninga, SG Ball, Cyril Connell, Harold Matthews).
    `parent_team_id` self-references to link a feeder team to its senior
    NRL/NRLW side. After mig 038, teams are referenced directly by
    typed FK (`team_id`) from association junctions and other tables —
    the polymorphic `entity_id` link to the dropped `entities` table is
    gone.
    """

    __tablename__ = "teams"

    team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    short_name: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    grade: Mapped[str] = mapped_column(Text, nullable=False)
    competition: Mapped[str | None] = mapped_column(Text)
    parent_team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.team_id", ondelete="SET NULL")
    )
    founded_year: Mapped[int | None] = mapped_column(Integer)
    logo_url: Mapped[str | None] = mapped_column(Text)
    nrlcom_team_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    parent: Mapped["Team | None"] = relationship("Team", remote_side=[team_id], backref="feeders")

    __table_args__ = (
        CheckConstraint(
            "grade IN ("
            "'nrl', 'nrlw', 'nsw_cup', 'qld_cup', "
            "'jersey_flegg', 'mal_meninga', 'sg_ball', "
            "'cyril_connell', 'harold_matthews'"
            ")",
            name="ck_teams_grade",
        ),
        CheckConstraint(
            "parent_team_id IS NULL OR parent_team_id <> team_id",
            name="ck_teams_grade_self_parent",
        ),
        Index("idx_teams_grade", "grade"),
        Index("idx_teams_parent", "parent_team_id"),
        Index("idx_teams_active", "active"),
    )


# ─── Identity tables ────────────────────────────────────────────────────
# After mig 038, the old Entity / EntityRole / PlayerAttributes tables and
# their classes are gone. Person + PlayerAttributes + PersonRole + Round
# are the canonical identity layer.


class Person(Base):
    """Unified table for every human actor — players, coaches, advisors,
    commentators, journalists, referees. Lifetime-stable facts get typed
    columns; long-tail goes in metadata_json. See migration 036.
    """

    __tablename__ = "people"

    person_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    slug: Mapped[str | None] = mapped_column(Text, unique=True)

    dob: Mapped[date | None] = mapped_column(Date)
    country: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    supercoach_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    nrlcom_player_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)

    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_people_name", "canonical_name"),
        Index("idx_people_country", "country", postgresql_where="country IS NOT NULL"),
    )


class PlayerAttributes(Base):
    """SCD-2 of slow-changing player facts (team, position, height,
    weight, contract, salary). Only player-class people land here;
    coach/referee/advisor tenures live in `people_roles`.

    Renamed from `people_attributes` in migration 068 — the table only
    ever carried player-shaped fields, so the new name is self-documenting.
    """

    __tablename__ = "player_attributes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.person_id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.team_id", ondelete="SET NULL")
    )
    primary_position: Mapped[str | None] = mapped_column(Text)
    height_cm: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[int | None] = mapped_column(Integer)
    contract_until: Mapped[date | None] = mapped_column(Date)
    real_salary_aud: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="seed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_player_attributes_period",
        ),
        Index("idx_player_attributes_person_current", "person_id", "is_current"),
        Index("idx_player_attributes_team_current", "team_id", "is_current"),
        Index(
            "uq_player_attributes_current",
            "person_id",
            unique=True,
            postgresql_where="is_current",
        ),
    )


class PersonRole(Base):
    """SCD-2 of role tenure per person. Multi-valued at a point in time
    (e.g. Adam Reynolds = active player + occasional commentator). Renamed
    from ``EntityRole`` (dropped in mig 037).
    """

    __tablename__ = "people_roles"

    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.person_id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="seed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('player', 'coach', 'commentator', 'journalist', 'referee', 'advisor')",
            name="ck_people_roles_role",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_people_roles_period",
        ),
        Index("idx_people_roles_person", "person_id", "effective_to"),
        Index("idx_people_roles_role_period", "role", "effective_from", "effective_to"),
        Index(
            "uq_people_roles_primary_current",
            "person_id",
            unique=True,
            postgresql_where="is_primary AND effective_to IS NULL",
        ),
    )


class Quote(Base):
    __tablename__ = "quotes"

    quote_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_documents.document_id"), nullable=False
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("source_chunks.chunk_id"))
    speaker_person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("people.person_id"))
    quoted_text: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    said_at_reference: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    document: Mapped["SourceDocument"] = relationship(back_populates="quotes")
    claims: Mapped[list["Claim"]] = relationship(back_populates="quote")

    __table_args__ = (
        Index("idx_quotes_document", "document_id"),
        Index("idx_quotes_speaker", "speaker_person_id"),
    )


class ClaimChunk(Base):
    __tablename__ = "claim_chunks"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.claim_id", ondelete="CASCADE"), primary_key=True
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_chunks.chunk_id", ondelete="CASCADE"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    claim: Mapped["Claim"] = relationship(back_populates="chunk_links")
    chunk: Mapped["SourceChunk"] = relationship(back_populates="claim_links")

    __table_args__ = (Index("idx_claim_chunks_chunk", "chunk_id"),)


class Claim(Base):
    __tablename__ = "claims"

    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_documents.document_id")
    )
    quote_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("quotes.quote_id"))
    claim_type: Mapped[str] = mapped_column(Text, nullable=False)
    claim_text: Mapped[str | None] = mapped_column(Text)
    polarity: Mapped[float | None] = mapped_column(Float)
    strength: Mapped[float | None] = mapped_column(Float)
    effective_round: Mapped[int | None] = mapped_column(Integer)
    season: Mapped[int | None] = mapped_column(Integer)
    start_ts: Mapped[float | None] = mapped_column(Float)
    end_ts: Mapped[float | None] = mapped_column(Float)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    document: Mapped["SourceDocument | None"] = relationship()
    quote: Mapped["Quote | None"] = relationship(back_populates="claims")
    chunk_links: Mapped[list["ClaimChunk"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    associations: Mapped[list["ClaimAssociation"]] = relationship(back_populates="claim", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "claim_type IN ("
            # Fantasy-actionable
            "'buy', 'sell', 'hold', 'captain', 'avoid', 'breakout', 'matchup_edge', "
            # Annotation-flavoured (mig 036; absorbed from source_annotations)
            "'mention', 'theme', 'subtopic', 'sentiment', 'tactical_tag', 'highlight'"
            ")",
            name="ck_claim_type",
        ),
        Index("idx_claims_type", "claim_type"),
        Index("idx_claims_document", "document_id"),
        Index("idx_claims_round_season", "effective_round", "season"),
    )


class ClaimAssociation(Base):
    """Polymorphic many-to-many between claims and typed entities.

    A claim can name a player + team + match all at once with different
    roles. The CHECK constraint enforces exactly one typed FK is set per
    row. See migration 036.
    """

    __tablename__ = "claim_associations"

    association_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.claim_id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.person_id", ondelete="CASCADE")
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.team_id", ondelete="CASCADE")
    )
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.match_id", ondelete="CASCADE")
    )
    venue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.venue_id", ondelete="CASCADE")
    )
    round_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rounds.round_id", ondelete="CASCADE")
    )

    claim: Mapped["Claim"] = relationship(back_populates="associations")

    __table_args__ = (
        CheckConstraint(
            "(person_id IS NOT NULL)::int + (team_id IS NOT NULL)::int + "
            "(match_id IS NOT NULL)::int + (venue_id IS NOT NULL)::int + "
            "(round_id IS NOT NULL)::int = 1",
            name="ck_claim_associations_one_subject",
        ),
        UniqueConstraint(
            "claim_id",
            "role",
            "person_id",
            "team_id",
            "match_id",
            "venue_id",
            "round_id",
            name="uq_claim_associations",
            postgresql_nulls_not_distinct=True,
        ),
        Index("idx_claim_associations_claim", "claim_id"),
        Index("idx_claim_associations_person", "person_id", postgresql_where="person_id IS NOT NULL"),
        Index("idx_claim_associations_team", "team_id", postgresql_where="team_id IS NOT NULL"),
        Index("idx_claim_associations_match", "match_id", postgresql_where="match_id IS NOT NULL"),
        Index("idx_claim_associations_venue", "venue_id", postgresql_where="venue_id IS NOT NULL"),
        Index("idx_claim_associations_round", "round_id", postgresql_where="round_id IS NOT NULL"),
    )


class Prediction(Base):
    __tablename__ = "predictions"

    prediction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    predictor_person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("people.person_id"))
    prediction_type: Mapped[str | None] = mapped_column(Text)
    predicted_value_text: Mapped[str | None] = mapped_column(Text)
    event_window: Mapped[str | None] = mapped_column(Text)
    evidence_claim_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_status: Mapped[str | None] = mapped_column(Text)

    associations: Mapped[list["PredictionAssociation"]] = relationship(
        back_populates="prediction", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_predictions_predictor", "predictor_person_id"),)


class PredictionAssociation(Base):
    """Polymorphic many-to-many between predictions and typed entities.
    See ``ClaimAssociation`` for shape rationale. Migration 036.
    """

    __tablename__ = "prediction_associations"

    association_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    prediction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("predictions.prediction_id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.person_id", ondelete="CASCADE")
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.team_id", ondelete="CASCADE")
    )
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.match_id", ondelete="CASCADE")
    )
    venue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.venue_id", ondelete="CASCADE")
    )
    round_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rounds.round_id", ondelete="CASCADE")
    )

    prediction: Mapped["Prediction"] = relationship(back_populates="associations")

    __table_args__ = (
        CheckConstraint(
            "(person_id IS NOT NULL)::int + (team_id IS NOT NULL)::int + "
            "(match_id IS NOT NULL)::int + (venue_id IS NOT NULL)::int + "
            "(round_id IS NOT NULL)::int = 1",
            name="ck_prediction_associations_one_subject",
        ),
        UniqueConstraint(
            "prediction_id",
            "role",
            "person_id",
            "team_id",
            "match_id",
            "venue_id",
            "round_id",
            name="uq_prediction_associations",
            postgresql_nulls_not_distinct=True,
        ),
        Index("idx_prediction_associations_prediction", "prediction_id"),
        Index("idx_prediction_associations_person", "person_id", postgresql_where="person_id IS NOT NULL"),
        Index("idx_prediction_associations_team", "team_id", postgresql_where="team_id IS NOT NULL"),
        Index("idx_prediction_associations_match", "match_id", postgresql_where="match_id IS NOT NULL"),
        Index("idx_prediction_associations_venue", "venue_id", postgresql_where="venue_id IS NOT NULL"),
        Index("idx_prediction_associations_round", "round_id", postgresql_where="round_id IS NOT NULL"),
    )


class ConsensusSnapshot(Base):
    __tablename__ = "consensus_snapshots"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("people.person_id"))
    team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.team_id"))
    match_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("matches.match_id"))
    venue_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("venues.venue_id"))
    round_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rounds.round_id"))
    time_bucket: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    buy_count: Mapped[int] = mapped_column(Integer, default=0)
    sell_count: Mapped[int] = mapped_column(Integer, default=0)
    hold_count: Mapped[int] = mapped_column(Integer, default=0)
    neutral_count: Mapped[int] = mapped_column(Integer, default=0)
    contrarian_score: Mapped[float | None] = mapped_column(Float)
    consensus_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_consensus_subject_time", "person_id", "time_bucket"),
        CheckConstraint(
            "(person_id IS NOT NULL)::int + (team_id IS NOT NULL)::int + "
            "(match_id IS NOT NULL)::int + (venue_id IS NOT NULL)::int + "
            "(round_id IS NOT NULL)::int = 1",
            name="ck_consensus_snapshots_subject",
        ),
    )


class Decision(Base):
    __tablename__ = "decisions"

    decision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    decision_type: Mapped[str] = mapped_column(Text, nullable=False)
    action_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    rationale_summary: Mapped[str | None] = mapped_column(Text)
    strategy_tag: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    public_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    associations: Mapped[list["DecisionAssociation"]] = relationship(
        back_populates="decision", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "decision_type IN ('trade', 'captain', 'start_sit', 'squad_structure', 'article_topic', 'reply')",
            name="ck_decision_type",
        ),
        Index("idx_decisions_type", "decision_type"),
    )


class DecisionAssociation(Base):
    """Polymorphic many-to-many between decisions and typed entities.
    See ``ClaimAssociation`` for shape rationale. Migration 036.
    """

    __tablename__ = "decision_associations"

    association_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("decisions.decision_id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.person_id", ondelete="CASCADE")
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.team_id", ondelete="CASCADE")
    )
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.match_id", ondelete="CASCADE")
    )
    venue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.venue_id", ondelete="CASCADE")
    )
    round_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rounds.round_id", ondelete="CASCADE")
    )

    decision: Mapped["Decision"] = relationship(back_populates="associations")

    __table_args__ = (
        CheckConstraint(
            "(person_id IS NOT NULL)::int + (team_id IS NOT NULL)::int + "
            "(match_id IS NOT NULL)::int + (venue_id IS NOT NULL)::int + "
            "(round_id IS NOT NULL)::int = 1",
            name="ck_decision_associations_one_subject",
        ),
        UniqueConstraint(
            "decision_id",
            "role",
            "person_id",
            "team_id",
            "match_id",
            "venue_id",
            "round_id",
            name="uq_decision_associations",
            postgresql_nulls_not_distinct=True,
        ),
        Index("idx_decision_associations_decision", "decision_id"),
        Index("idx_decision_associations_person", "person_id", postgresql_where="person_id IS NOT NULL"),
        Index("idx_decision_associations_team", "team_id", postgresql_where="team_id IS NOT NULL"),
        Index("idx_decision_associations_match", "match_id", postgresql_where="match_id IS NOT NULL"),
        Index("idx_decision_associations_venue", "venue_id", postgresql_where="venue_id IS NOT NULL"),
        Index("idx_decision_associations_round", "round_id", postgresql_where="round_id IS NOT NULL"),
    )


class Plan(Base):
    __tablename__ = "plans"

    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    round_number: Mapped[int | None] = mapped_column(Integer)
    plan_summary: Mapped[str | None] = mapped_column(Text)
    scenario_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class Event(Base):
    __tablename__ = "events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    related_entity_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    related_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("decisions.decision_id")
    )
    related_prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("predictions.prediction_id")
    )
    related_claim_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    related_source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.source_id"))
    display_text: Mapped[str] = mapped_column(Text, nullable=False)
    display_mode: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    visibility: Mapped[str] = mapped_column(Text, nullable=False, default="public")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    immutable_hash: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "display_mode IN ('watching', 'signal', 'thinking', 'prediction', 'action', 'review', 'sys', 'question', 'answer')",  # noqa: E501  # SQL CHECK constraint — keep on one line for grep'ability
            name="ck_display_mode",
        ),
        CheckConstraint("visibility IN ('public', 'private')", name="ck_visibility"),
        Index("idx_events_type", "event_type"),
        Index("idx_events_created", "created_at"),
        Index("idx_events_visibility", "visibility"),
    )

    def compute_hash(self) -> str:
        payload = json.dumps(
            {
                "event_id": str(self.event_id),
                "event_type": self.event_type,
                "display_text": self.display_text,
                "created_at": self.created_at.isoformat() if self.created_at else "",
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()


class PlayerRound(Base):
    __tablename__ = "player_rounds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    player_id: Mapped[int] = mapped_column(Integer, nullable=False)
    player_name: Mapped[str] = mapped_column(Text, nullable=False)
    team: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[str] = mapped_column(Text, nullable=False)
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int | None] = mapped_column(Integer)
    price: Mapped[int | None] = mapped_column(Integer)
    breakeven: Mapped[int | None] = mapped_column(Integer)
    minutes: Mapped[int | None] = mapped_column(Integer)
    selected_pct: Mapped[float | None] = mapped_column(Float)

    # SC Breakdown
    base: Mapped[int | None] = mapped_column(Integer)
    attack: Mapped[int | None] = mapped_column(Integer)
    playmaking: Mapped[int | None] = mapped_column(Integer)
    power: Mapped[int | None] = mapped_column(Integer)
    negative: Mapped[int | None] = mapped_column(Integer)

    # Scoring
    tries: Mapped[int | None] = mapped_column(Integer)
    try_assists: Mapped[int | None] = mapped_column(Integer)
    goals: Mapped[int | None] = mapped_column(Integer)
    missed_goals: Mapped[int | None] = mapped_column(Integer)
    field_goals: Mapped[int | None] = mapped_column(Integer)
    missed_field_goals: Mapped[int | None] = mapped_column(Integer)

    # Attack
    line_breaks: Mapped[int | None] = mapped_column(Integer)
    line_break_assists: Mapped[int | None] = mapped_column(Integer)
    last_touch: Mapped[int | None] = mapped_column(Integer)
    tackle_busts: Mapped[int | None] = mapped_column(Integer)
    offloads: Mapped[int | None] = mapped_column(Integer)
    ineffective_offloads: Mapped[int | None] = mapped_column(Integer)
    hitups_8m: Mapped[int | None] = mapped_column(Integer)
    hitups_under_8m: Mapped[int | None] = mapped_column(Integer)
    kick_metres: Mapped[int | None] = mapped_column(Integer)

    # Defence
    tackles_made: Mapped[int | None] = mapped_column(Integer)
    missed_tackles: Mapped[int | None] = mapped_column(Integer)
    intercepts: Mapped[int | None] = mapped_column(Integer)

    # Discipline
    forced_dropouts: Mapped[int | None] = mapped_column(Integer)
    forty_twentys: Mapped[int | None] = mapped_column(Integer)
    kicked_dead: Mapped[int | None] = mapped_column(Integer)
    penalties: Mapped[int | None] = mapped_column(Integer)
    errors: Mapped[int | None] = mapped_column(Integer)
    sin_bins: Mapped[int | None] = mapped_column(Integer)
    handover_given: Mapped[int | None] = mapped_column(Integer)

    # Derived
    ppm: Mapped[float | None] = mapped_column(Float)
    base_ppm: Mapped[float | None] = mapped_column(Float)
    base_power: Mapped[int | None] = mapped_column(Integer)
    base_power_ppm: Mapped[float | None] = mapped_column(Float)

    # Averages
    avg_score: Mapped[float | None] = mapped_column(Float)
    two_rd_avg: Mapped[float | None] = mapped_column(Float)
    three_rd_avg: Mapped[float | None] = mapped_column(Float)
    five_rd_avg: Mapped[float | None] = mapped_column(Float)
    season_avg: Mapped[float | None] = mapped_column(Float)

    # Percentages
    hitup_8m_pct: Mapped[float | None] = mapped_column(Float)
    tackle_bust_pct: Mapped[float | None] = mapped_column(Float)
    missed_tackle_pct: Mapped[float | None] = mapped_column(Float)
    offload_involvement_pct: Mapped[float | None] = mapped_column(Float)
    base_pct: Mapped[float | None] = mapped_column(Float)

    # Price
    start_price: Mapped[int | None] = mapped_column(Integer)
    end_price: Mapped[int | None] = mapped_column(Integer)
    round_price_change: Mapped[int | None] = mapped_column(Integer)
    season_price_change: Mapped[int | None] = mapped_column(Integer)
    magic_number: Mapped[int | None] = mapped_column(Integer)

    # Context
    opposition: Mapped[str | None] = mapped_column(Text)
    venue: Mapped[str | None] = mapped_column(Text)
    weather: Mapped[str | None] = mapped_column(Text)
    surface: Mapped[str | None] = mapped_column(Text)
    jersey: Mapped[int | None] = mapped_column(Integer)
    bye_round: Mapped[str | None] = mapped_column(Text)

    # Canonical FKs — populated on writes after migration 032. Older rows
    # remain NULL; the legacy `team`/`opposition`/`venue` text columns
    # stay valid for historical queries.
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.match_id", ondelete="SET NULL")
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.team_id", ondelete="SET NULL")
    )

    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("player_id", "round", "season", name="uq_player_round_season"),
        Index("idx_player_rounds_season_round", "season", "round"),
        Index("idx_player_rounds_player", "player_id"),
        Index(
            "idx_player_rounds_match",
            "match_id",
            postgresql_where="match_id IS NOT NULL",
        ),
        Index(
            "idx_player_rounds_team",
            "team_id",
            postgresql_where="team_id IS NOT NULL",
        ),
    )


class Venue(Base):
    """Stadium reference table.

    Small, slow-changing. Referenced by ``Match.venue_id``. Seeded from
    ``data/venues.yaml`` via ``make seed-venues`` — see migration 028.
    """

    __tablename__ = "venues"

    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    city: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str] = mapped_column(Text, nullable=False, default="AU")
    capacity: Mapped[int | None] = mapped_column(Integer)
    surface: Mapped[str | None] = mapped_column(Text)
    roof: Mapped[str | None] = mapped_column(Text)
    tz: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    opened_year: Mapped[int | None] = mapped_column(Integer)
    image_url: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "surface IS NULL OR surface IN ('grass', 'hybrid', 'synthetic')",
            name="ck_venues_surface",
        ),
        CheckConstraint(
            "roof IS NULL OR roof IN ('open', 'closed', 'retractable')",
            name="ck_venues_roof",
        ),
        Index("idx_venues_active", "active"),
        Index("idx_venues_country_state", "country", "state"),
    )


class Round(Base):
    """Round identity. Replaces ``entity_type='round'`` rows on ``entities``.

    Linked to from ``claim_associations`` / ``prediction_associations`` /
    ``decision_associations`` when an opinion is round-level rather than
    player- or match-level. See migration 036.
    """

    __tablename__ = "rounds"

    round_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    round_number: Mapped[int | None] = mapped_column(Integer)
    round_label: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_magic_round: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_rep_weekend: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_finals: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("season", "round_number", name="uq_rounds_season_round"),
        Index("idx_rounds_season", "season"),
    )


class Match(Base):
    """Fixture / result spine — one row per game across all grades.

    Real-world side of the model; ``PlayerRound`` is the SuperCoach
    overlay that joins via ``match_id``. ``external_match_id`` + ``source``
    is the upsert key for the daily fixture sync — see migration 029.
    """

    __tablename__ = "matches"

    match_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)

    source: Mapped[str] = mapped_column(Text, nullable=False, default="nrl_com")
    external_match_id: Mapped[str | None] = mapped_column(Text)

    season: Mapped[int] = mapped_column(Integer, nullable=False)
    round: Mapped[int | None] = mapped_column(Integer)
    round_label: Mapped[str | None] = mapped_column(Text)
    grade: Mapped[str] = mapped_column(Text, nullable=False)

    home_team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.team_id", ondelete="RESTRICT"), nullable=False
    )
    # Nullable since mig 036: bye rows have status='bye' and away_team_id IS NULL.
    # `home_team_id` for bye rows is overloaded — it just means "the team in question."
    away_team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.team_id", ondelete="RESTRICT")
    )
    venue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.venue_id", ondelete="SET NULL")
    )

    kickoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False, default="scheduled")

    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)

    weather: Mapped[str | None] = mapped_column(Text)
    referee_name: Mapped[str | None] = mapped_column(Text)
    broadcast: Mapped[str | None] = mapped_column(Text)
    attendance: Mapped[int | None] = mapped_column(Integer)
    ground_conditions: Mapped[str | None] = mapped_column(Text)
    is_magic_round: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_rep_weekend: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "grade IN ("
            "'nrl', 'nrlw', 'nsw_cup', 'qld_cup', "
            "'jersey_flegg', 'mal_meninga', 'sg_ball', "
            "'cyril_connell', 'harold_matthews'"
            ")",
            name="ck_matches_grade",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'live', 'final', 'postponed', 'cancelled', 'forfeit', 'bye')",
            name="ck_matches_status",
        ),
        CheckConstraint(
            "(status='bye' AND away_team_id IS NULL) OR (status<>'bye' AND away_team_id IS NOT NULL)",
            name="ck_matches_bye_no_opponent",
        ),
        CheckConstraint(
            "home_team_id <> away_team_id",
            name="ck_matches_distinct_teams",
        ),
        CheckConstraint(
            "(home_score IS NULL AND away_score IS NULL) OR (home_score IS NOT NULL AND away_score IS NOT NULL)",
            name="ck_matches_score_paired",
        ),
        Index(
            "uq_matches_source_external",
            "source",
            "season",
            "grade",
            "external_match_id",
            unique=True,
            postgresql_where="external_match_id IS NOT NULL",
        ),
        Index("idx_matches_season_round_grade", "season", "round", "grade"),
        Index("idx_matches_kickoff", "kickoff_at"),
        Index("idx_matches_status", "status"),
        Index("idx_matches_home_team", "home_team_id"),
        Index("idx_matches_away_team", "away_team_id"),
        Index("idx_matches_venue", "venue_id"),
    )


class MatchTeamList(Base):
    """Versioned named-17 announcement per match per team.

    Each new public lineup release (Tuesday list, Thursday list, late
    changes) appends a row with an incremented ``list_version`` rather
    than mutating the prior row. Query the latest version to see the
    live lineup; query the full history to see how it shifted.

    See migration 030.
    """

    __tablename__ = "match_team_lists"

    list_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.match_id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.team_id", ondelete="RESTRICT"), nullable=False
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.person_id", ondelete="RESTRICT"), nullable=False
    )

    jersey_number: Mapped[int | None] = mapped_column(Integer)
    named_position: Mapped[str | None] = mapped_column(Text)
    sc_position: Mapped[str | None] = mapped_column(Text)
    is_captain: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    list_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="named")
    announced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(Text, nullable=False, default="nrl_com")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('named', 'late_change_in', 'late_change_out', '19th_man', 'reserve', 'withdrawn')",
            name="ck_match_team_lists_status",
        ),
        CheckConstraint(
            "jersey_number IS NULL OR (jersey_number BETWEEN 1 AND 30)",
            name="ck_match_team_lists_jersey_range",
        ),
        UniqueConstraint(
            "match_id",
            "team_id",
            "player_id",
            "list_version",
            name="uq_match_team_lists_match_team_player_version",
        ),
        Index("idx_match_team_lists_match", "match_id"),
        Index("idx_match_team_lists_team", "team_id"),
        Index("idx_match_team_lists_player", "player_id"),
        Index(
            "idx_match_team_lists_match_team_version",
            "match_id",
            "team_id",
            "list_version",
        ),
    )


class Injury(Base):
    """Append-on-change injury / suspension timeline.

    A new row lands when a player's casualty-ward state changes. Resolving
    an injury is recorded by both writing a new row with status='cleared'
    *and* setting ``resolved_at`` on the prior open row. See migration 031.
    """

    __tablename__ = "injuries"

    injury_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.person_id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.team_id", ondelete="SET NULL")
    )

    status: Mapped[str] = mapped_column(Text, nullable=False)
    body_part: Mapped[str | None] = mapped_column(Text)
    mechanism: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)

    expected_return_round: Mapped[int | None] = mapped_column(Integer)
    expected_return_date: Mapped[date | None] = mapped_column(Date)
    severity: Mapped[str | None] = mapped_column(Text)

    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('training', 'test', '1_week', '2_4_weeks', '4_8_weeks', "
            "'indefinite', 'season', 'suspended', 'cleared')",
            name="ck_injuries_status",
        ),
        CheckConstraint(
            "severity IS NULL OR severity IN ('low', 'moderate', 'high', 'season')",
            name="ck_injuries_severity",
        ),
        CheckConstraint(
            "mechanism IS NULL OR mechanism IN ("
            "'collision', 'non_contact', 'illness', "
            "'concussion_protocol', 'suspension', 'unknown')",
            name="ck_injuries_mechanism",
        ),
        Index("idx_injuries_player_reported", "player_id", "reported_at"),
        Index(
            "idx_injuries_team_status",
            "team_id",
            "status",
            postgresql_where="resolved_at IS NULL",
        ),
        Index("idx_injuries_reported_at", "reported_at"),
    )


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    kb_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    kb_type: Mapped[str] = mapped_column(Text, nullable=False)
    person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("people.person_id"))
    team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.team_id"))
    match_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("matches.match_id"))
    venue_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("venues.venue_id"))
    round_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rounds.round_id"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1536))
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    effective_round: Mapped[int | None] = mapped_column(Integer)
    season: Mapped[int | None] = mapped_column(Integer)
    source_claim_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "kb_type IN ('player_summary', 'round_brief', 'decision', 'opinion', 'source_digest', "
            "'article_tips', 'article_totw', 'article_trades', "
            "'article_captains', 'article_stocks', 'article_consensus')",
            name="ck_kb_type",
        ),
        Index("idx_kb_type", "kb_type"),
        Index("idx_kb_person", "person_id"),
        CheckConstraint(
            "(person_id IS NOT NULL)::int + (team_id IS NOT NULL)::int + "
            "(match_id IS NOT NULL)::int + (venue_id IS NOT NULL)::int + "
            "(round_id IS NOT NULL)::int <= 1",
            name="ck_knowledge_base_subject",
        ),
        Index("idx_kb_round_season", "effective_round", "season"),
    )


class WikiPage(Base):
    __tablename__ = "wiki_pages"

    page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    channel_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channels.channel_id"))
    person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("people.person_id"))
    team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.team_id"))
    match_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("matches.match_id"))
    venue_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("venues.venue_id"))
    round_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rounds.round_id"))
    page_type: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="stub")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    revisions: Mapped[list["WikiRevision"]] = relationship(back_populates="page", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "page_type IN ('player', 'team', 'advisor', 'round', 'channel')",
            name="ck_wiki_page_type",
        ),
        CheckConstraint("status IN ('stub', 'draft', 'published')", name="ck_wiki_status"),
        CheckConstraint(
            "(person_id IS NOT NULL)::int + (team_id IS NOT NULL)::int + "
            "(match_id IS NOT NULL)::int + (venue_id IS NOT NULL)::int + "
            "(round_id IS NOT NULL)::int + (channel_id IS NOT NULL)::int = 1",
            name="ck_wiki_page_subject",
        ),
        Index("idx_wiki_pages_type", "page_type"),
        Index("idx_wiki_pages_slug", "slug"),
        Index("idx_wiki_pages_channel", "channel_id"),
        Index("idx_wiki_pages_updated", "updated_at"),
        Index("idx_wiki_pages_status", "status"),
    )


class WikiRevision(Base):
    __tablename__ = "wiki_revisions"

    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_pages.page_id", ondelete="CASCADE"), nullable=False
    )
    section_heading: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    content_snapshot: Mapped[str | None] = mapped_column(Text)
    source_trigger: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.source_id"))
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    page: Mapped["WikiPage"] = relationship(back_populates="revisions")

    __table_args__ = (
        Index("idx_wiki_revisions_page", "page_id", "created_at"),
        Index("idx_wiki_revisions_created", "created_at"),
    )


class AgentEvent(Base):
    """Per-event audit trail for Claude-Agent-SDK-based agents.

    Live-queryable store for the JSONL event stream that gets uploaded to S3
    at run end. One row per event; dense `sequence` per run for ordered replay.
    See `docs/agents/system/agent-audit.md` for the standard event types.
    """

    __tablename__ = "agent_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    run_id: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    t: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    turn: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_agent_events_run_sequence"),
        Index("idx_agent_events_run", "run_id", "sequence"),
        Index("idx_agent_events_agent_t", "agent_id", "t"),
        Index("idx_agent_events_type", "type"),
    )


class AgentRun(Base):
    """Run-level summary for Claude-Agent-SDK-based agents.

    One row per run, keyed by `run_id`. Inserted with status='running' at the
    top of a run and updated in place at run end with totals, summary, and
    cost rollup. Joined to `agent_events` (the per-event trail) via `run_id`.

    Token columns are rolled up from `agent_events.payload->'usage'`. Cost
    columns are estimated via `jeromelu_shared.agent_audit.estimate_*` — used
    for budget gates and observability, not invoicing.
    """

    __tablename__ = "agent_runs"

    run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    model: Mapped[str | None] = mapped_column(Text)
    brief_preview: Mapped[str | None] = mapped_column(Text)
    bounds_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    detail_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    s3_log_key: Mapped[str | None] = mapped_column(Text)
    agent_events_count: Mapped[int | None] = mapped_column(Integer)

    turns_used: Mapped[int | None] = mapped_column(Integer)
    tool_calls: Mapped[int | None] = mapped_column(Integer)

    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer)

    token_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6))
    server_tool_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6))
    total_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6))

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'aborted', 'failed')",
            name="ck_agent_runs_status",
        ),
        CheckConstraint(
            "agent_id IN ('miner', 'presenter_miner', 'scribe', 'analyst', 'stats', 'fixtures')",
            name="ck_agent_runs_agent_id",
        ),
        Index("idx_agent_runs_agent_started", "agent_id", "started_at"),
        Index("idx_agent_runs_started", "started_at"),
        Index(
            "idx_agent_runs_status_running",
            "started_at",
            postgresql_where="status = 'running'",
        ),
    )


class SquadSlot(Base):
    __tablename__ = "squad_slots"

    slot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    position: Mapped[str] = mapped_column(Text, nullable=False)
    slot_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # player FK dropped with entities (mig 038). Returns as `player_id` → people
    # when the SuperCoach squad feature is built.
    player_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_captain: Mapped[bool] = mapped_column(Boolean, default=False)
    is_vice_captain: Mapped[bool] = mapped_column(Boolean, default=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    conviction: Mapped[str] = mapped_column(Text, default="medium")
    added_round: Mapped[int | None] = mapped_column(Integer)
    season: Mapped[int] = mapped_column(Integer, default=2026)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint("conviction IN ('low', 'medium', 'high')", name="ck_squad_conviction"),
        CheckConstraint(
            "position IN ('FLB', 'CTW', '5/8', 'HFB', 'HOK', 'FRF', '2RF', 'FLX')",
            name="ck_squad_position",
        ),
        Index("idx_squad_season", "season"),
    )


class SquadTrade(Base):
    __tablename__ = "squad_trades"

    trade_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    decision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("decisions.decision_id"))
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    season: Mapped[int] = mapped_column(Integer, default=2026)
    # Player FKs were dropped with entities (mig 038). Squad tables are planned-
    # not-built; the typed FKs (e.g. player_out_id → people) get added back
    # when the SuperCoach squad feature ships.
    player_out_name: Mapped[str] = mapped_column(Text, nullable=False)
    player_in_name: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_squad_trades_round", "round", "season"),
        Index("idx_squad_trades_created", "created_at"),
    )


class Outcome(Base):
    __tablename__ = "outcomes"

    outcome_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    prediction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("predictions.prediction_id"))
    decision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("decisions.decision_id"))
    actual_value_json: Mapped[dict | None] = mapped_column(JSONB)
    result_label: Mapped[str | None] = mapped_column(Text)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class MinerCandidate(Base):
    """Miner's candidate inbox.

    Miner (the source-discovery agent) writes here as it hunts the web for
    new NRL channels and videos worth onboarding. Humans approve or reject
    via the admin review queue; approval promotes a row into the canonical
    ``channels`` (kind=channel) or ``sources`` (kind=video) tables.

    Distinct from ``sources`` so unapproved noise does not pollute the main
    pipeline. Renamed from ``discovered_sources`` in migration 035.
    """

    __tablename__ = "miner_candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False, default="youtube")
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    channel_external_id: Mapped[str | None] = mapped_column(Text)
    content_categories: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    score: Mapped[float | None] = mapped_column(Float)
    score_reasons: Mapped[list] = mapped_column(JSONB, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    discovered_via: Mapped[str] = mapped_column(Text, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_note: Mapped[str | None] = mapped_column(Text)
    promoted_channel_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channels.channel_id"))
    run_id: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("kind IN ('channel', 'video')", name="ck_miner_candidates_kind"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'snoozed', 'duplicate')",
            name="ck_miner_candidates_status",
        ),
        UniqueConstraint(
            "platform",
            "kind",
            "external_id",
            name="uq_miner_candidates_platform_kind_external",
        ),
        Index("idx_miner_candidates_status", "status"),
        Index("idx_miner_candidates_kind", "kind"),
        Index("idx_miner_candidates_run", "run_id"),
        Index("idx_miner_candidates_at", "discovered_at"),
    )


class ChannelMetric(Base):
    """Time-series popularity metrics per channel.

    Multi-platform via the JSONB `metrics` column — YouTube uses
    {subscribers, videos, views, country, channel_published_at}; other
    platforms (podcast, twitter) carry their own shape. See migration 023.

    For "current state" queries, prefer the `channel_latest_metrics` view
    over scanning this table.
    """

    __tablename__ = "channel_metrics"

    metric_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channels.channel_id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("channel_id", "sampled_at", name="uq_channel_metrics_channel_sampled"),
        Index("idx_channel_metrics_channel_time", "channel_id", "sampled_at"),
        Index("idx_channel_metrics_platform_time", "platform", "sampled_at"),
        Index("idx_channel_metrics_sampled_at", "sampled_at"),
    )


class VideoMetric(Base):
    """Time-series popularity metrics per video (a `sources` row).

    Sibling of ChannelMetric. YouTube payload shape:
    {views, likes, comments, duration_seconds}. Sampled at video discovery
    time (channel approval) and daily thereafter via the admin refresh
    endpoint.

    For "current state" queries prefer the `video_latest_metrics` view.
    """

    __tablename__ = "video_metrics"

    metric_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.source_id", ondelete="CASCADE"), nullable=False
    )
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("source_id", "sampled_at", name="uq_video_metrics_source_sampled"),
        Index("idx_video_metrics_source_time", "source_id", "sampled_at"),
        Index("idx_video_metrics_sampled_at", "sampled_at"),
    )


class MinerPresenterCandidate(Base):
    """Presenter Miner's staging inbox.

    The Presenter Miner agent researches a channel's regular presenters via
    web search and files each finding here. Humans confirm/reject in the
    admin review surface; confirmation creates (or links) a `people` row
    and writes a `source_presenters` association. See migration 052 and
    docs/todo/source-presenters.md.
    """

    __tablename__ = "miner_presenter_candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channels.channel_id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    llm_confidence: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    existing_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.person_id", ondelete="SET NULL")
    )

    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    confirmed_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.person_id", ondelete="SET NULL")
    )

    run_id: Mapped[str | None] = mapped_column(Text)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "role IN ('host','co-host','regular','frequent-guest')",
            name="ck_miner_pres_role",
        ),
        CheckConstraint(
            "status IN ('pending','confirmed','rejected')",
            name="ck_miner_pres_status",
        ),
        Index("idx_miner_pres_channel_status", "channel_id", "status"),
    )


class SourcePresenter(Base):
    """Confirmed presenter ↔ channel association.

    Anchored at channel level — presenters are a property of the show, not
    the episode. A guest on one source is not a presenter; they only land
    here once a reviewer confirms them as a regular. See migration 052.
    """

    __tablename__ = "source_presenters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channels.channel_id", ondelete="CASCADE"), nullable=False
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.person_id", ondelete="CASCADE"), nullable=False
    )

    role: Mapped[str] = mapped_column(Text, nullable=False)
    is_regular: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    since_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    confirmed_by: Mapped[str | None] = mapped_column(Text)
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("miner_presenter_candidates.id", ondelete="SET NULL"),
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('host','co-host','regular','frequent-guest')",
            name="ck_src_pres_role",
        ),
        UniqueConstraint("channel_id", "person_id", name="uq_src_pres_channel_person"),
        Index("idx_src_pres_person", "person_id"),
    )
