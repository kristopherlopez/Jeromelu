# LLM Architecture

## Principle
Do not use one giant prompt for everything.
That will become sloppy fast.

Use role-specific LLM tasks.

## Suggested LLM Task Types

### 1. Extraction Models
Used for:
- entity extraction
- quote extraction
- claim / prediction extraction
- matchup tagging

Output must be structured JSON.

### 2. Synthesis Models
Used for:
- consensus summaries
- narrative summaries
- plan recaps

### 3. Characterisation Models
Used for:
- converting internal state into Jaromelu voice
- generating live feed thoughts
- generating chat replies

**Implementation: Feed Generation** (`services/worker-publishing/app/activities/generate_events.py`)
- Converts structured claims into opinionated feed events in Jaromelu's voice
- Uses `chat_json()` from `packages/shared/jeromelu_shared/llm.py` (gpt-4o, temp 0.2, JSON mode)
- Full details: `docs/pages/feed/generation.md` → LLM Infrastructure section

### 4. Review Models
Used for:
- checking whether output violates tone or safety constraints
- verifying evidence lineage exists

## Hierarchical Agent Orchestration

For complex transcript analysis, use a multi-agent hierarchy instead of a single monolithic prompt. This pattern applies whenever the input is too large or too varied for one context window to handle well.

### Pattern: Chapter → Specialist → Verify

```
Orchestrator (Sonnet)
├── Detects semantic chapters from lightweight scan
├── Produces chapter manifest with boundaries + enrichment hints
│
├── Specialist Agent 1 (Opus) — game_review, scoped to 2 teams
├── Specialist Agent 2 (Opus) — position_analysis, scoped to positions
├── Specialist Agent N (Opus) — each with fresh context + enrichment
│   └── Returns: sub-topics + name corrections + claims
│
└── Verification Agents (Haiku) — one per claim, parallel
    └── Returns: PASS/FLAG/FAIL per field
```

### Key Principles

1. **Progressive context**: Don't dump everything at once. Orchestrator scans broadly, specialists dive deep into their slice.
2. **Scoped enrichment**: Each specialist gets only the data relevant to its chapter — player pools filtered by team/position, fixture data for the specific match.
3. **Fresh context per chapter**: Instead of one 30KB+ context, each specialist gets 2-5KB of focused text. Quality stays high across long transcripts.
4. **Model tiering**: Use expensive models (Opus) for deep reasoning, cheaper models (Sonnet) for classification, cheapest (Haiku) for bounded verification.

### Implementation

- Skill: `/analyse-transcript` (`.claude/skills/analyse-transcript/skill.md`)
- Full pipeline docs: `docs/agents/skills/analyse-transcript.md`

## Retrieval Pattern
For public Q&A and public thought generation:
- retrieve structured facts first
- retrieve source quotes second
- retrieve recent plans third
- then generate

The model should not invent consensus.
It should cite lineage internally before speaking.
