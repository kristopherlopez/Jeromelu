import hashlib
import json
import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
    creator_name: Mapped[str | None] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(Text, unique=True)
    approved_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ingestion_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    channel: Mapped["Channel | None"] = relationship(back_populates="sources")
    documents: Mapped[list["SourceDocument"]] = relationship(back_populates="source", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("source_type IN ('youtube', 'podcast', 'web', 'radio', 'manual')", name="ck_source_type"),
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

    __table_args__ = (
        Index("idx_source_documents_source", "source_id"),
    )


class SourceChunk(Base):
    __tablename__ = "source_chunks"

    chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("source_documents.document_id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    embedding = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    document: Mapped["SourceDocument"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("idx_source_chunks_document", "document_id"),
    )


class Entity(Base):
    __tablename__ = "entities"

    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        CheckConstraint("entity_type IN ('player', 'team', 'expert', 'matchup')", name="ck_entity_type"),
        Index("idx_entities_type", "entity_type"),
        Index("idx_entities_name", "canonical_name"),
    )


class Quote(Base):
    __tablename__ = "quotes"

    quote_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("source_documents.document_id"), nullable=False)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("source_chunks.chunk_id"))
    speaker_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.entity_id"))
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
        Index("idx_quotes_speaker", "speaker_entity_id"),
    )


class Claim(Base):
    __tablename__ = "claims"

    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    quote_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("quotes.quote_id"))
    subject_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.entity_id"))
    claim_type: Mapped[str] = mapped_column(Text, nullable=False)
    polarity: Mapped[float | None] = mapped_column(Float)
    strength: Mapped[float | None] = mapped_column(Float)
    effective_round: Mapped[int | None] = mapped_column(Integer)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    quote: Mapped["Quote | None"] = relationship(back_populates="claims")

    __table_args__ = (
        CheckConstraint(
            "claim_type IN ('buy', 'sell', 'hold', 'captain', 'avoid', 'breakout', 'matchup_edge')",
            name="ck_claim_type",
        ),
        Index("idx_claims_subject", "subject_entity_id"),
        Index("idx_claims_type", "claim_type"),
    )


class Prediction(Base):
    __tablename__ = "predictions"

    prediction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    predictor_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.entity_id"))
    subject_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.entity_id"))
    prediction_type: Mapped[str | None] = mapped_column(Text)
    predicted_value_text: Mapped[str | None] = mapped_column(Text)
    event_window: Mapped[str | None] = mapped_column(Text)
    evidence_claim_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_status: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("idx_predictions_predictor", "predictor_entity_id"),
        Index("idx_predictions_subject", "subject_entity_id"),
    )


class ConsensusSnapshot(Base):
    __tablename__ = "consensus_snapshots"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    subject_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False)
    time_bucket: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    buy_count: Mapped[int] = mapped_column(Integer, default=0)
    sell_count: Mapped[int] = mapped_column(Integer, default=0)
    hold_count: Mapped[int] = mapped_column(Integer, default=0)
    neutral_count: Mapped[int] = mapped_column(Integer, default=0)
    contrarian_score: Mapped[float | None] = mapped_column(Float)
    consensus_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_consensus_subject_time", "subject_entity_id", "time_bucket"),
    )


class Decision(Base):
    __tablename__ = "decisions"

    decision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    decision_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.entity_id"))
    action_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    rationale_summary: Mapped[str | None] = mapped_column(Text)
    strategy_tag: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    public_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint(
            "decision_type IN ('trade', 'captain', 'start_sit', 'squad_structure', 'article_topic', 'reply')",
            name="ck_decision_type",
        ),
        Index("idx_decisions_type", "decision_type"),
    )


class Plan(Base):
    __tablename__ = "plans"

    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    round_number: Mapped[int | None] = mapped_column(Integer)
    plan_summary: Mapped[str | None] = mapped_column(Text)
    scenario_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class Event(Base):
    __tablename__ = "events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    related_entity_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    related_decision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("decisions.decision_id"))
    related_prediction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("predictions.prediction_id"))
    display_text: Mapped[str] = mapped_column(Text, nullable=False)
    display_mode: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(Text, nullable=False, default="public")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    immutable_hash: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("display_mode IN ('thought', 'action', 'system', 'prediction', 'review')", name="ck_display_mode"),
        CheckConstraint("visibility IN ('public', 'private')", name="ck_visibility"),
        Index("idx_events_type", "event_type"),
        Index("idx_events_created", "created_at"),
        Index("idx_events_visibility", "visibility"),
    )

    def compute_hash(self) -> str:
        payload = json.dumps({
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "display_text": self.display_text,
            "created_at": self.created_at.isoformat() if self.created_at else "",
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()


class Outcome(Base):
    __tablename__ = "outcomes"

    outcome_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    prediction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("predictions.prediction_id"))
    decision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("decisions.decision_id"))
    actual_value_json: Mapped[dict | None] = mapped_column(JSONB)
    result_label: Mapped[str | None] = mapped_column(Text)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
