-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- sources
CREATE TABLE sources (
    source_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type VARCHAR(20) NOT NULL CHECK (source_type IN ('youtube', 'podcast', 'web', 'radio', 'manual')),
    title TEXT NOT NULL,
    creator_name TEXT,
    canonical_url TEXT UNIQUE,
    approved_flag BOOLEAN NOT NULL DEFAULT FALSE,
    ingestion_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    published_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- source_documents
CREATE TABLE source_documents (
    document_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL REFERENCES sources(source_id),
    raw_text TEXT,
    cleaned_text TEXT,
    transcript_available BOOLEAN NOT NULL DEFAULT FALSE,
    language VARCHAR(10) DEFAULT 'en',
    checksum VARCHAR(64),
    chunk_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- source_chunks
CREATE TABLE source_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES source_documents(document_id),
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    start_offset INTEGER,
    end_offset INTEGER,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- entities
CREATE TABLE entities (
    entity_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('player', 'team', 'expert', 'matchup')),
    canonical_name TEXT NOT NULL,
    aliases TEXT[] DEFAULT '{}',
    metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- quotes
CREATE TABLE quotes (
    quote_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES source_documents(document_id),
    chunk_id UUID REFERENCES source_chunks(chunk_id),
    speaker_entity_id UUID REFERENCES entities(entity_id),
    quoted_text TEXT NOT NULL,
    start_offset INTEGER,
    end_offset INTEGER,
    said_at_reference TEXT,
    confidence REAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- claims
CREATE TABLE claims (
    claim_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quote_id UUID REFERENCES quotes(quote_id),
    subject_entity_id UUID REFERENCES entities(entity_id),
    claim_type VARCHAR(20) NOT NULL CHECK (claim_type IN ('buy', 'sell', 'hold', 'captain', 'avoid', 'breakout', 'matchup_edge')),
    polarity REAL,
    strength REAL,
    effective_round INTEGER,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- predictions
CREATE TABLE predictions (
    prediction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    predictor_entity_id UUID REFERENCES entities(entity_id),
    subject_entity_id UUID REFERENCES entities(entity_id),
    prediction_type VARCHAR(50),
    predicted_value_text TEXT,
    event_window TEXT,
    evidence_claim_ids UUID[] DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolution_status VARCHAR(20)
);

-- consensus_snapshots
CREATE TABLE consensus_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_entity_id UUID NOT NULL REFERENCES entities(entity_id),
    time_bucket TIMESTAMPTZ NOT NULL,
    buy_count INTEGER DEFAULT 0,
    sell_count INTEGER DEFAULT 0,
    hold_count INTEGER DEFAULT 0,
    neutral_count INTEGER DEFAULT 0,
    contrarian_score REAL,
    consensus_score REAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- decisions
CREATE TABLE decisions (
    decision_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    decision_type VARCHAR(30) NOT NULL CHECK (decision_type IN ('trade', 'captain', 'start_sit', 'squad_structure', 'article_topic', 'reply')),
    subject_entity_id UUID REFERENCES entities(entity_id),
    action_json JSONB NOT NULL DEFAULT '{}',
    rationale_summary TEXT,
    strategy_tag VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    executed_at TIMESTAMPTZ,
    public_flag BOOLEAN NOT NULL DEFAULT FALSE
);

-- plans
CREATE TABLE plans (
    plan_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    round_number INTEGER,
    plan_summary TEXT,
    scenario_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- events
CREATE TABLE events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(50) NOT NULL,
    related_entity_ids UUID[] DEFAULT '{}',
    related_decision_id UUID REFERENCES decisions(decision_id),
    related_prediction_id UUID REFERENCES predictions(prediction_id),
    display_text TEXT NOT NULL,
    display_mode VARCHAR(20) NOT NULL CHECK (display_mode IN ('thought', 'action', 'system', 'prediction', 'review')),
    visibility VARCHAR(10) NOT NULL DEFAULT 'public' CHECK (visibility IN ('public', 'private')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    immutable_hash VARCHAR(64)
);

-- outcomes
CREATE TABLE outcomes (
    outcome_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prediction_id UUID REFERENCES predictions(prediction_id),
    decision_id UUID REFERENCES decisions(decision_id),
    actual_value_json JSONB,
    result_label VARCHAR(20),
    scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_sources_type ON sources(source_type);
CREATE INDEX idx_sources_approved ON sources(approved_flag);
CREATE INDEX idx_source_documents_source ON source_documents(source_id);
CREATE INDEX idx_source_chunks_document ON source_chunks(document_id);
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_name ON entities(canonical_name);
CREATE INDEX idx_quotes_document ON quotes(document_id);
CREATE INDEX idx_quotes_speaker ON quotes(speaker_entity_id);
CREATE INDEX idx_claims_subject ON claims(subject_entity_id);
CREATE INDEX idx_claims_type ON claims(claim_type);
CREATE INDEX idx_predictions_predictor ON predictions(predictor_entity_id);
CREATE INDEX idx_predictions_subject ON predictions(subject_entity_id);
CREATE INDEX idx_consensus_subject_time ON consensus_snapshots(subject_entity_id, time_bucket);
CREATE INDEX idx_decisions_type ON decisions(decision_type);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_created ON events(created_at);
CREATE INDEX idx_events_visibility ON events(visibility);
