-- 011: Knowledge base table for Ask Me RAG
-- Curated, distilled knowledge entries that JeromeLu draws from when answering questions.
-- Maintained by the KB generation Temporal workflow.

CREATE TABLE knowledge_base (
    kb_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_type           TEXT NOT NULL,
    subject_entity_id UUID REFERENCES entities(entity_id),
    title             TEXT NOT NULL,
    content           TEXT NOT NULL,
    embedding         vector(1536),
    metadata_json     JSONB DEFAULT '{}',
    effective_round   INT,
    season            INT,
    source_claim_ids  UUID[] DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at        TIMESTAMPTZ,

    CONSTRAINT ck_kb_type CHECK (
        kb_type IN ('player_summary', 'round_brief', 'decision', 'opinion', 'source_digest')
    )
);

CREATE INDEX idx_kb_type ON knowledge_base(kb_type);
CREATE INDEX idx_kb_entity ON knowledge_base(subject_entity_id);
CREATE INDEX idx_kb_round_season ON knowledge_base(effective_round, season);
CREATE INDEX idx_kb_embedding ON knowledge_base
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
