-- Extend knowledge_base types to support insight articles
ALTER TABLE knowledge_base DROP CONSTRAINT IF EXISTS ck_kb_type;
ALTER TABLE knowledge_base ADD CONSTRAINT ck_kb_type CHECK (
    kb_type IN (
        'player_summary', 'round_brief', 'decision', 'opinion', 'source_digest',
        'article_tips', 'article_totw', 'article_trades',
        'article_captains', 'article_stocks', 'article_consensus'
    )
);
