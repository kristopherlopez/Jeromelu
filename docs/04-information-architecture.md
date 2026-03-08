# Information Architecture

## Core Objects
The system revolves around structured entities:
- Source
- Episode / article / transcript
- Quote
- Expert
- Player
- Team
- Matchup
- Opinion
- Prediction
- Decision
- Event
- Plan
- Outcome

## Lineage Principle
Every meaningful opinion or claim should trace back to the exact source words.

That means the system stores:
- raw transcript / raw article text
- source metadata
- extracted quote spans
- entity links
- derived opinions
- timestamps

Nothing important should exist without provenance.

## Public State
Visible to users:
- team and roster state
- trade history
- decision rationale
- predictions
- expert tracking
- consensus tracking
- event timeline

## Private State
Internal only:
- candidate rankings
- orchestration status
- moderation flags
- confidence / uncertainty internals
- hidden operator controls
- system prompts and policies

---

# Data Model

## Recommended Schema

### sources
- source_id
- source_type (youtube, podcast, web, radio, manual)
- title
- creator_name
- canonical_url
- approved_flag
- ingestion_status
- published_at
- ingested_at

### source_documents
- document_id
- source_id
- raw_text
- cleaned_text
- transcript_available
- language
- checksum
- chunk_count

### source_chunks
- chunk_id
- document_id
- chunk_index
- text
- start_offset
- end_offset
- embedding

### entities
- entity_id
- entity_type (player, team, expert, matchup)
- canonical_name
- aliases
- metadata_json

### quotes
- quote_id
- document_id
- chunk_id
- speaker_entity_id
- quoted_text
- start_offset
- end_offset
- said_at_reference
- confidence

### claims
- claim_id
- quote_id
- subject_entity_id
- claim_type (buy, sell, hold, captain, avoid, breakout, matchup edge)
- polarity
- strength
- effective_round
- extracted_at

### predictions
- prediction_id
- predictor_entity_id
- subject_entity_id
- prediction_type
- predicted_value_text
- event_window
- evidence_claim_ids
- created_at
- resolved_at
- resolution_status

### consensus_snapshots
- snapshot_id
- subject_entity_id
- time_bucket
- buy_count
- sell_count
- hold_count
- neutral_count
- contrarian_score
- consensus_score

### decisions
- decision_id
- decision_type (trade, captain, start_sit, squad_structure, article_topic, reply)
- subject_entity_id
- action_json
- rationale_summary
- strategy_tag
- created_at
- executed_at
- public_flag

### plans
- plan_id
- status
- round_number
- plan_summary
- scenario_json
- updated_at

### events
- event_id
- event_type
- related_entity_ids
- related_decision_id
- related_prediction_id
- display_text
- display_mode (thought, action, system, prediction, review)
- visibility
- created_at
- immutable_hash

### outcomes
- outcome_id
- prediction_id or decision_id
- actual_value_json
- result_label
- scored_at

This schema is enough for V1 and does not overcomplicate things.
