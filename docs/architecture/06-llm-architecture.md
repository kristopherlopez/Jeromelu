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
- converting internal state into Jeromelu voice
- generating live feed thoughts
- generating chat replies

### 4. Review Models
Used for:
- checking whether output violates tone or safety constraints
- verifying evidence lineage exists

## Retrieval Pattern
For public Q&A and public thought generation:
- retrieve structured facts first
- retrieve source quotes second
- retrieve recent plans third
- then generate

The model should not invent consensus.
It should cite lineage internally before speaking.
