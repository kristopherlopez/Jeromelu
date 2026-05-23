---
tags: [area/pages, subarea/feed]
---

# Feed Generation

The feed generation pipeline converts extracted claims into opinionated, first-person feed events written in Jaromelu's voice. It runs on a 30-minute Temporal schedule, reads unprocessed claims from the database, synthesises them via LLM, and persists deduplicated `Event` rows that the frontend renders as the activity feed.

```
Claims (from transcript extraction)
    |
    v
[Temporal: every 30 mins]
    |
    v
1. Fetch Unprocessed Claims ──> 2. Update Consensus ──> 3. Generate Reviews
                                                              |
                                                              v
                                                    4. LLM Event Synthesis
                                                              |
                                                              v
                                                    5. Persist Events (dedup)
                                                              |
                                                              v
                                              GET /api/feed ──> /feed page
```

---

## Event Types

Every feed item has an `event_type` and matching `display_mode`. The 9 types map to what Jaromelu is doing:

| Type | Icon | What it represents | Example |
|------|------|--------------------|---------|
| `watching` | Eye | Reacting to what a source said | "Just watched KingOfSC. He's pushing Cleary hard." |
| `signal` | TrendingUp | Consensus shift — multiple sources now agree | "Three sources in a row selling Hynes. That's not noise anymore." |
| `thinking` | Brain | Analysis connecting claims to data | "The numbers say hold on Munster. The matchup says sell." |
| `prediction` | Target | Bold call with conviction | "Calling it now: Mam outscores Cleary this week." |
| `action` | Zap | Trade decision or captain lock | "Trade locked in. Gutho out, Mam in." |
| `review` | RotateCcw | Past prediction reviewed against actual scores | "That Munster captain call aged badly. 34 points." |
| `sys` | Settings | Pipeline activity summary | "Scanned 6 new episodes. 22 claims extracted." |
| `question` | MessageCircle | User question from the chat input | "Should I trade Cleary this week?" |
| `answer` | BotMessageSquare | Jaromelu's RAG-powered response to a question | "Cleary's breakeven is 42..." |

### How claim types map to event types

| Claim Pattern | → Event Type |
|---|---|
| Single source buy/sell/hold/avoid | `watching` |
| 3+ sources agree on same entity | `signal` |
| captain/breakout/matchup_edge analysis | `thinking` |
| High-strength breakout or bold claim | `prediction` |
| Multiple buy/sell converging on a trade | `action` |
| Past prediction vs actual player_rounds score | `review` |
| Ingestion batch summary | `sys` |

---

## Pipeline Activities

### Activity 1: Fetch Unprocessed Claims

Finds claims not yet referenced by any event's `related_claim_ids`.

- Queries `claims` table, excluding claim IDs already in `events.related_claim_ids`
- Joins entity names and source/creator info for the LLM prompt
- Returns structured dict: `{claims, entity_map, source_map}`

**File**: `services/worker-publishing/app/activities/generate_events.py` → `fetch_unprocessed_claims()`

### Activity 2: Update Consensus Snapshots

Aggregates claim sentiment per entity and detects narrative shifts.

- Queries claims extracted since the last `ConsensusSnapshot`
- Groups by `subject_entity_id`, counts buy/sell/hold
- Computes `consensus_score` = max(buy, sell, hold) / total
- Compares to previous snapshot — flags entities where the dominant sentiment flipped
- Inserts new `ConsensusSnapshot` rows

**Output**: list of flipped entities `[{entity_id, canonical_name, old_dominant, new_dominant}]`

**File**: `services/worker-publishing/app/activities/update_consensus.py` → `update_consensus_snapshots()`

### Activity 3: Generate Review Data

Compares past predictions against actual player performance.

- Queries `predictions` not yet reviewed (no matching review event with `related_prediction_id`)
- Looks up `player_rounds` for the subject entity's most recent completed round
- Returns structured review data: `{prediction_text, actual_score, player_name, ...}`

**File**: `services/worker-publishing/app/activities/generate_reviews.py` → `generate_review_data()`

### Activity 4: LLM Event Synthesis

Calls OpenAI via `chat_json()` to generate Jaromelu-voiced feed items.

- **System prompt**: Voice rules (first-person, opinionated, NRL jargon, short punchy sentences)
- **User prompt**: JSON payload with claims, consensus shifts, and review data
- **Response**: JSON array of event objects with `event_type`, `display_text`, entity/claim references
- Validates response against allowed event types
- Resolves entity names back to UUIDs
- Caps at ~8 events per batch to prevent feed spam

**File**: `services/worker-publishing/app/activities/generate_events.py` → `generate_feed_events()`

---

## LLM Infrastructure

Activity 4 is the core LLM call. Here's the full chain:

```
generate_feed_events()                           # Activity in generate_events.py
    → chat_json(SYSTEM_PROMPT, user_prompt)       # Shared helper in jeromelu_shared/llm.py
        → OpenAI chat.completions.create()        # gpt-4o, response_format: json_object, temp 0.2
```

### Shared module

**File**: `packages/shared/jeromelu_shared/llm.py`

```python
chat_json(system_prompt: str, user_prompt: str, model: str = "gpt-4o") -> dict
```

- Uses the OpenAI Python SDK with `api_key` from `jeromelu_shared.config.settings.openai_api_key`
- Forces `response_format: {"type": "json_object"}` so the response is always parseable
- Temperature `0.2` for consistent, low-variance output
- Returns the parsed JSON dict directly

### System prompt

Defined as `SYSTEM_PROMPT` in `services/worker-publishing/app/activities/generate_events.py`.

Sets Jaromelu's voice rules:
- First person ("I", "I'm", "my")
- Short punchy sentences, max 2-3 per item
- NRL SuperCoach jargon (breakeven, PPM, base stats, ceiling, floor)
- Opinionated — take a side, don't sit on the fence
- Reference player names exactly as provided
- Source attribution with "via {creator}" style

Defines the 7 event types and when to use each one.

### User prompt

JSON payload built from the three preceding activities:

```json
{
  "claims": [
    {
      "claim_id": "uuid",
      "claim_type": "buy",
      "claim_text": "...",
      "polarity": 0.8,
      "strength": 0.9,
      "player_name": "Nathan Cleary",
      "entity_id": "uuid",
      "source_id": "uuid",
      "source_title": "SC Round 5 Preview",
      "source_creator": "KingOfSC",
      "effective_round": 5,
      "season": 2026
    }
  ],
  "consensus_shifts": [
    {"entity_id": "uuid", "canonical_name": "Nicho Hynes", "old_dominant": "hold", "new_dominant": "sell"}
  ],
  "reviews": [
    {"prediction_id": "uuid", "prediction_text": "...", "player_name": "Cameron Munster", "actual_score": 34}
  ]
}
```

### Expected response

```json
{
  "events": [
    {
      "event_type": "watching",
      "display_text": "Just watched KingOfSC. He's pushing Cleary hard. Everyone is. I'm not buying the panic.",
      "related_entity_names": ["Nathan Cleary"],
      "related_claim_ids": ["uuid"],
      "related_source_id": "uuid",
      "metadata": {}
    }
  ]
}
```

After parsing, the activity validates `event_type` against the 7 allowed values, resolves `related_entity_names` back to entity UUIDs via the `entity_map`, and caps at ~8 events per batch.

### Architecture classification

This is a **Characterisation Model** per `docs/architecture/03-llm-architecture.md` — it converts internal state (structured claims) into Jaromelu's voice for the live feed.

---

### Activity 5: Persist Events

Writes Event rows to the database with deduplication.

- Computes `immutable_hash` from `(event_type, display_text, sorted related_claim_ids)`
- Skips if hash already exists — safe to re-run the workflow without duplicates
- Inserts new `Event` rows with all provenance fields

**File**: `services/worker-publishing/app/activities/generate_events.py` → `persist_events()`

---

## Temporal Workflow

**Workflow**: `FeedGenerationWorkflow`
**Queue**: `publishing`
**Schedule**: Every 30 minutes
**Timeout**: 5 minutes per LLM call, 2 minutes for DB activities
**Retry**: 3 attempts, 5s initial, 2x backoff

The workflow is idempotent — re-running it processes only new claims and deduplicates on persist.

**File**: `services/worker-publishing/app/workflows/feed_generation.py`

---

## Feed API

**Endpoint**: `GET /api/feed`

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Page size (max 200) |
| `before` | ISO datetime | — | Cursor for pagination |
| `filter` | string | — | `thoughts`, `actions`, or `predictions` |
| `entity_id` | UUID | — | Filter to events mentioning a specific player |

**Filter groups**:
- `thoughts` → `watching`, `signal`, `thinking`, `review`
- `actions` → `action`, `sys`
- `predictions` → `prediction`
- `chat` → `question`, `answer`

**Response**:
```json
{
  "items": [
    {
      "id": "uuid",
      "type": "watching",
      "text": "Just watched KingOfSC...",
      "timestamp": "2026-03-22T10:00:00Z",
      "players": [{"name": "Nathan Cleary", "entityId": "uuid"}],
      "source": {"title": "SC Round 5", "sourceId": "uuid", "creator": "KingOfSC"},
      "prediction": null
    }
  ],
  "next_before": "2026-03-21T14:00:00Z"
}
```

The router batch-loads entities, sources, and predictions to resolve references efficiently.

**File**: `services/api/app/routers/feed.py`

### Ask endpoint (Twitch-style chat)

**Endpoint**: `POST /api/feed/ask`

Users can ask Jaromelu questions directly from the feed. Both the question and answer are persisted as feed events, creating a Twitch-style flat timeline where chat and generated content coexist.

| Field | Type | Description |
|-------|------|-------------|
| `question` | string | User's question (max 500 chars) |
| `temperature` | string | `straight`, `sharp`, or `roast` |

**Response**:
```json
{
  "question_item": { ...feed item... },
  "answer_item": { ...feed item... }
}
```

The endpoint creates two events:
1. A `question` event with the user's text
2. An `answer` event with the RAG response, player references, and source attribution in `metadata_json`

**File**: `services/api/app/routers/feed.py`

---

## Deduplication

Two layers prevent duplicate feed content:

| Layer | Check | Where |
|-------|-------|-------|
| Claims | `related_claim_ids` on events | Only unprocessed claims enter the LLM |
| Events | `immutable_hash` | SHA-256 of (event_type, display_text, claim_ids) |

---

## Database

### Events table (extended)

The `events` table has three provenance columns added in migration `010`:

| Column | Type | Purpose |
|--------|------|---------|
| `related_claim_ids` | UUID[] | Claim UUIDs that triggered this event |
| `related_source_id` | UUID FK | Originating source (for "via Creator" attribution) |
| `metadata_json` | JSONB | Flexible storage (review outcomes, prediction details) |

### Display modes

```
watching | signal | thinking | prediction | action | review | sys | question | answer
```

---

## File Structure

```
services/worker-publishing/app/
├── workflows/
│   └── feed_generation.py           # FeedGenerationWorkflow
├── activities/
│   ├── generate_events.py           # fetch, synthesise, persist
│   ├── generate_reviews.py          # compare predictions to scores
│   └── update_consensus.py          # aggregate sentiment, detect flips
└── main.py                          # Worker entry point

services/api/app/
└── routers/
    └── feed.py                      # GET /api/feed

services/web/src/app/feed/
├── page.tsx                         # Server-side fetch from API
├── FeedClient.tsx                   # Client component with filters
├── FeedItemCard.tsx                 # Individual item rendering
└── feed-data.ts                     # TypeScript types
```
