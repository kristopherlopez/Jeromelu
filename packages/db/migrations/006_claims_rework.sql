-- Rework claims: direct lineage to documents/chunks, many-to-many chunk linkage,
-- claim text, season, and video timestamps on chunks.

-- 1. Add claim_text, document_id, and season to claims
ALTER TABLE claims
    ADD COLUMN claim_text TEXT,
    ADD COLUMN document_id UUID REFERENCES source_documents(document_id),
    ADD COLUMN season INTEGER;

CREATE INDEX idx_claims_document ON claims(document_id);
CREATE INDEX idx_claims_round_season ON claims(effective_round, season);

-- 2. Join table: claim <-> source_chunks (many-to-many)
CREATE TABLE claim_chunks (
    claim_id UUID NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    chunk_id UUID NOT NULL REFERENCES source_chunks(chunk_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (claim_id, chunk_id)
);

CREATE INDEX idx_claim_chunks_chunk ON claim_chunks(chunk_id);

-- 3. Add video timestamps to source_chunks
ALTER TABLE source_chunks
    ADD COLUMN start_ts REAL,
    ADD COLUMN end_ts REAL;
