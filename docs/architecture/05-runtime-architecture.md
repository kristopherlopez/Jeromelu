# Runtime Architecture

## System Topology

### A. Source Discovery Layer
Purpose:
Find new candidate content.

Functions:
- poll known channels / feeds / sites
- discover new episodes or articles
- deduplicate by URL and checksum
- queue for approval or automatic ingestion

Output:
New source records.

### B. Source Approval Layer
Purpose:
Prevent garbage ingestion.

Modes:
- pre-approved source list
- admin approval queue for new creators / sites
- source health rules

This matters because bad inputs will poison the brand.

### C. Ingestion Layer
Purpose:
Fetch and store raw content.

Functions:
- transcript retrieval
- article extraction
- normalisation
- metadata capture
- chunking
- raw text storage

V1 rule:
Store the full raw transcript permanently.

### D. Extraction Layer
Purpose:
Turn raw text into structured knowledge.

Functions:
- entity recognition
- quote extraction
- opinion extraction
- prediction extraction
- matchup extraction
- speaker attribution
- claim normalisation

Output:
quotes, claims, predictions, linked entities.

### E. Knowledge Layer
Purpose:
Provide queryable state for the rest of the product.

Contains:
- relational store for structured facts
- vector store for semantic retrieval
- consensus snapshot builder
- expert performance history

### F. Decision Engine
V1 choice:
Rules + heuristics.

Inputs:
- consensus signals
- matchup narratives
- public stats / fixture context later
- prior Jaromelu plans
- current squad state

Outputs:
- candidate moves
- preferred moves
- public-facing rationale
- deliberate contrarian moves when allowed

Important:
Contrarian behaviour should be policy-bounded, not random.
It should only occur inside safe thresholds.

### G. Orchestration Layer
Purpose:
Run the system as a chain of workflows.

Supports:
- scheduled jobs
- event-triggered jobs
- workflow-to-workflow triggering
- retries
- dead-letter queues
- audit logs

Typical flows:
1. discover source -> ingest -> extract -> update consensus -> publish thought
2. injury news -> inject event -> re-evaluate plans -> publish update
3. weekly deadline window -> generate options -> choose move -> publish decision

### H. Publishing Layer
Purpose:
Convert machine state into public experience.

Produces:
- live feed events
- team dashboard updates
- prediction ledger updates
- chat answers
- war room state
- article drafts later

### I. Admin / Operator Layer
Needs on day one:
- source approvals
- manual event injection
- pause decision engine
- pause publishing
- replay event generation
- moderation queue
- entity correction / merge tools
- emergency kill switch

### J. Frontend Experience Layer
Recommended shape:
Mostly static website shell with dynamic modules.

Why:
- simpler to build
- easier SEO
- enough for near-real-time
- avoids overengineering early

Dynamic modules:
- live feed
- team state
- war room panels
- chat
- opinion explorer
