-- Replace source_chunks.text with raw_text and clean_text columns
ALTER TABLE source_chunks RENAME COLUMN text TO raw_text;
ALTER TABLE source_chunks ADD COLUMN clean_text TEXT;
