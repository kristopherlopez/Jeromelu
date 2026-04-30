import hashlib
import json
import uuid
from datetime import date, datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
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
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    clean_text: Mapped[str | None] = mapped_column(Text)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    start_ts: Mapped[float | None] = mapped_column(Float)
    end_ts: Mapped[float | None] = mapped_column(Float)
    embedding = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    document: Mapped["SourceDocument"] = relationship(back_populates="chunks")
    claim_links: Mapped[list["ClaimChunk"]] = relationship(back_populates="chunk")

    __table_args__ = (
        Index("idx_source_chunks_document", "document_id"),
    )


class Entity(Base):
    __tablename__ = "entities"

    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    slug: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    roles: Mapped[list["EntityRole"]] = relationship(back_populates="entity", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ("
            "'player', 'team', 'advisor', 'coach', 'referee', "
            "'commentator', 'journalist', 'matchup', 'round'"
            ")",
            name="ck_entity_type",
        ),
        Index("idx_entities_type", "entity_type"),
        Index("idx_entities_name", "canonical_name"),
    )


class Team(Base):
    """Canonical roster of every team across all grades feeding into NRL.

    Covers NRL, NRLW, and the male pathway feeders (NSW Cup, QLD Cup,
    Jersey Flegg, Mal Meninga, SG Ball, Cyril Connell, Harold Matthews).
    `parent_team_id` self-references to link a feeder team to its senior
    NRL/NRLW side; `entity_id` links senior rows to the canonical
    `entities` row so existing claims/predictions/wiki pages keep
    working without duplication.
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
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id", ondelete="SET NULL"), unique=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

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
        Index("idx_teams_entity", "entity_id"),
        Index("idx_teams_active", "active"),
    )


class EntityRole(Base):
    __tablename__ = "entity_roles"

    entity_role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="seed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    entity: Mapped["Entity"] = relationship(back_populates="roles")

    __table_args__ = (
        CheckConstraint(
            "role IN ('player', 'coach', 'commentator', 'journalist', 'referee', 'advisor')",
            name="ck_entity_roles_role",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_entity_roles_period",
        ),
        Index("idx_entity_roles_entity", "entity_id", "effective_to"),
        Index("idx_entity_roles_role_period", "role", "effective_from", "effective_to"),
        Index(
            "uq_entity_roles_primary_current",
            "entity_id",
            unique=True,
            postgresql_where="is_primary AND effective_to IS NULL",
        ),
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


class ClaimChunk(Base):
    __tablename__ = "claim_chunks"

    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.claim_id", ondelete="CASCADE"), primary_key=True)
    chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("source_chunks.chunk_id", ondelete="CASCADE"), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    claim: Mapped["Claim"] = relationship(back_populates="chunk_links")
    chunk: Mapped["SourceChunk"] = relationship(back_populates="claim_links")

    __table_args__ = (
        Index("idx_claim_chunks_chunk", "chunk_id"),
    )


class Claim(Base):
    __tablename__ = "claims"

    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("source_documents.document_id"))
    quote_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("quotes.quote_id"))
    subject_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.entity_id"))
    claim_type: Mapped[str] = mapped_column(Text, nullable=False)
    claim_text: Mapped[str | None] = mapped_column(Text)
    polarity: Mapped[float | None] = mapped_column(Float)
    strength: Mapped[float | None] = mapped_column(Float)
    effective_round: Mapped[int | None] = mapped_column(Integer)
    season: Mapped[int | None] = mapped_column(Integer)
    start_ts: Mapped[float | None] = mapped_column(Float)
    end_ts: Mapped[float | None] = mapped_column(Float)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    document: Mapped["SourceDocument | None"] = relationship()
    quote: Mapped["Quote | None"] = relationship(back_populates="claims")
    chunk_links: Mapped[list["ClaimChunk"]] = relationship(back_populates="claim", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "claim_type IN ('buy', 'sell', 'hold', 'captain', 'avoid', 'breakout', 'matchup_edge')",
            name="ck_claim_type",
        ),
        Index("idx_claims_subject", "subject_entity_id"),
        Index("idx_claims_type", "claim_type"),
        Index("idx_claims_document", "document_id"),
        Index("idx_claims_round_season", "effective_round", "season"),
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
    related_claim_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    related_source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.source_id"))
    display_text: Mapped[str] = mapped_column(Text, nullable=False)
    display_mode: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    visibility: Mapped[str] = mapped_column(Text, nullable=False, default="public")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    immutable_hash: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("display_mode IN ('watching', 'signal', 'thinking', 'prediction', 'action', 'review', 'sys', 'question', 'answer')", name="ck_display_mode"),
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

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("player_id", "round", "season", name="uq_player_round_season"),
        Index("idx_player_rounds_season_round", "season", "round"),
        Index("idx_player_rounds_player", "player_id"),
    )


class PlayerAttributes(Base):
    """SCD-2 of slow-changing player facts.

    Replaces ``player_team_history`` (migration 005). Carries team
    affiliation, primary position, physical (height, weight) and contract
    facts. All change at the same beats — preseason, transfer window,
    contract renewal — so a single SCD-2 row per current state is cleaner
    than parallel temporal tables.

    Per-round facts (price, breakeven, score, jersey, grade) live in
    :class:`PlayerRound`; lifetime constants in ``entities.metadata_json``;
    cross-entity-type role tenure in :class:`EntityRole`.
    """

    __tablename__ = "player_attributes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id", ondelete="CASCADE"), nullable=False
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
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_player_attributes_period",
        ),
        Index("idx_player_attributes_entity_current", "entity_id", "is_current"),
        Index("idx_player_attributes_team_current", "team_id", "is_current"),
        Index(
            "uq_player_attributes_current",
            "entity_id",
            unique=True,
            postgresql_where="is_current",
        ),
    )


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    kb_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    kb_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.entity_id"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1536))
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    effective_round: Mapped[int | None] = mapped_column(Integer)
    season: Mapped[int | None] = mapped_column(Integer)
    source_claim_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "kb_type IN ('player_summary', 'round_brief', 'decision', 'opinion', 'source_digest', "
            "'article_tips', 'article_totw', 'article_trades', "
            "'article_captains', 'article_stocks', 'article_consensus')",
            name="ck_kb_type",
        ),
        Index("idx_kb_type", "kb_type"),
        Index("idx_kb_entity", "subject_entity_id"),
        Index("idx_kb_round_season", "effective_round", "season"),
    )


class WikiPage(Base):
    __tablename__ = "wiki_pages"

    page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.entity_id"))
    channel_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channels.channel_id"))
    page_type: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="stub")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    revisions: Mapped[list["WikiRevision"]] = relationship(back_populates="page", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "page_type IN ('player', 'team', 'advisor', 'round', 'channel')",
            name="ck_wiki_page_type",
        ),
        CheckConstraint("status IN ('stub', 'draft', 'published')", name="ck_wiki_status"),
        CheckConstraint(
            "(entity_id IS NOT NULL AND channel_id IS NULL) "
            "OR (entity_id IS NULL AND channel_id IS NOT NULL)",
            name="ck_wiki_page_subject",
        ),
        Index("idx_wiki_pages_type", "page_type"),
        Index("idx_wiki_pages_slug", "slug"),
        Index("idx_wiki_pages_entity", "entity_id"),
        Index("idx_wiki_pages_channel", "channel_id"),
        Index("idx_wiki_pages_updated", "updated_at"),
        Index("idx_wiki_pages_status", "status"),
    )


class WikiRevision(Base):
    __tablename__ = "wiki_revisions"

    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wiki_pages.page_id", ondelete="CASCADE"), nullable=False)
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
            "agent_id IN ('scout', 'scribe', 'analyst', 'stats', 'fixtures')",
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
    player_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.entity_id"))
    player_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_captain: Mapped[bool] = mapped_column(Boolean, default=False)
    is_vice_captain: Mapped[bool] = mapped_column(Boolean, default=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    conviction: Mapped[str] = mapped_column(Text, default="medium")
    added_round: Mapped[int | None] = mapped_column(Integer)
    season: Mapped[int] = mapped_column(Integer, default=2026)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        CheckConstraint("conviction IN ('low', 'medium', 'high')", name="ck_squad_conviction"),
        CheckConstraint(
            "position IN ('FLB', 'CTW', '5/8', 'HFB', 'HOK', 'FRF', '2RF', 'FLX')",
            name="ck_squad_position",
        ),
        Index("idx_squad_player", "player_entity_id"),
        Index("idx_squad_season", "season"),
    )


class SquadTrade(Base):
    __tablename__ = "squad_trades"

    trade_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    decision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("decisions.decision_id"))
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    season: Mapped[int] = mapped_column(Integer, default=2026)
    player_out_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.entity_id"))
    player_out_name: Mapped[str] = mapped_column(Text, nullable=False)
    player_in_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.entity_id"))
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


class DiscoveredSource(Base):
    __tablename__ = "discovered_sources"

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
        CheckConstraint("kind IN ('channel', 'video')", name="ck_discovered_kind"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'snoozed', 'duplicate')",
            name="ck_discovered_status",
        ),
        UniqueConstraint("platform", "kind", "external_id", name="uq_discovered_platform_kind_external"),
        Index("idx_discovered_status", "status"),
        Index("idx_discovered_kind", "kind"),
        Index("idx_discovered_run", "run_id"),
        Index("idx_discovered_at", "discovered_at"),
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
    time (channel approval) and weekly thereafter via the admin refresh
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
