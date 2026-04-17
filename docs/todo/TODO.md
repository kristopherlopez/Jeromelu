# Jaromelu — Master To-Do

Substantive architecture docs with completed work are split out (linked below). Everything else lives inline here.

---

## Phase 1 — Prove the Brain (Intelligence Layer)

### 1.1 Temporal Orchestration Setup

Architecture and implementation: [temporal-orchestration.md](temporal-orchestration.md).

### 1.2 Ingestion Worker

Architecture, S3 format, and MVP task list: [ingestion-worker.md](ingestion-worker.md).

### 1.3 Extraction Worker

Design decisions and the local-first validation plan: [extraction-worker.md](extraction-worker.md).

### 1.4 Consensus Engine

- [ ] Aggregate claims into per-player consensus snapshots (buy/sell/hold counts)
- [ ] Time-bucketed snapshots (daily, weekly)
- [ ] Compute `contrarian_score` and `consensus_score`
- [ ] Track consensus shifts over time
- [ ] Expert accuracy tracking — score experts on prediction outcomes

### 1.5 Database Layer

- [x] SQLAlchemy ORM models for all 12 tables — `packages/shared/jeromelu_shared/db/models.py`
- [x] Shared database module — `packages/shared/` pip-installable package
- [x] Connection pooling and session management — `packages/shared/jeromelu_shared/db/session.py`
- [ ] Alembic migration runner for future schema changes

---

## Phase 2 — Prove the Character (Personality + Experience)

### 2.1 Decision Worker (`services/worker-decision`)

- [ ] Rule-based decision engine — transparent heuristics, no black box
- [ ] Candidate move generator — enumerate viable trades, captain picks, structure changes
- [ ] Move scoring via heuristics (consensus signals, matchup data, squad constraints)
- [ ] Move ranking and selection
- [ ] Rationale generation — explain why each decision was made
- [ ] Policy-bounded contrarian override system
- [ ] Squad state management — track current team, trades remaining, budget
- [ ] Strategic planning — round-by-round plans with scenario modeling
- [ ] Assumption invalidation detection — detect when plans need rebuilding
- [ ] Temporal workflows: `WeeklyDecisionWorkflow`, `StrategyRefreshWorkflow`

### 2.2 Publishing Worker (`services/worker-publishing`)

- [ ] Live feed event generation — convert system state changes into feed events
- [ ] Event types: `source_ingested`, `opinion_extracted`, `narrative_shift`, `prediction`, `trade_decision`, `match_review`
- [ ] Jaromelu voice layer — LLM characterisation to write in Jaromelu's voice
- [ ] Tone/temperature control (straight, sharp, lightly roasting)
- [ ] Display modes: thought, action, system, prediction, review
- [ ] Immutable event hashing for audit trail
- [ ] Temporal workflow: `PublishingWorkflow`

### 2.3 Match Review System

- [ ] Collect actual match outcomes (scores, player points) — data source TBD
- [ ] Compare predictions vs actuals
- [ ] Score prediction accuracy (hits/misses)
- [ ] Update expert accuracy leaderboard
- [ ] Publish match review events to feed
- [ ] Temporal workflow: `MatchReviewWorkflow`

---

## Phase 3 — API & Frontend

### 3.1 API Endpoints (`services/api`)

- [ ] `GET /feed` — paginated live feed events
- [ ] `GET /feed/latest` — latest events (polling/SSE)
- [ ] `GET /team` — current squad state
- [ ] `GET /team/history` — trade history, captain choices
- [ ] `GET /predictions` — prediction ledger
- [ ] `GET /predictions/{id}` — prediction detail with evidence
- [ ] `GET /consensus/{player_id}` — player consensus data
- [ ] `GET /entities/players` — player list with search
- [ ] `GET /entities/players/{id}` — player profile with claims, predictions
- [ ] `GET /entities/experts` — expert list with accuracy scores
- [ ] `GET /sources` — source list
- [ ] `POST /chat` — Ask Jaromelu (chat interface)
- [ ] Authentication / API key middleware
- [ ] Rate limiting
- [ ] Error handling and validation

### 3.2 Frontend Pages (`services/web`)

- [x] **The Feed** — live event stream (core product surface), `/`
- [x] **The Wiki** — agent-maintained knowledge base, `/wiki`
- [x] **The Ledger** — prediction tracking, `/ledger`
- [x] **The Analysis** — editorial articles, `/insights`
- [x] **Ask Me** — merged into Feed as Twitch-style chat; Q&A persisted as feed events with temperature control
- [ ] Responsive design / mobile-friendly pass across all pages
- [ ] SEO metadata for public pages

### 3.3 Admin Interface

- [ ] Source approval queue
- [ ] Manual event injection (breaking news, corrections)
- [ ] Pause/resume decision and publishing engines
- [ ] Entity correction/merge tools
- [ ] Emergency kill switch + system prompt controls

---

## Phase 4 — Infrastructure & Operations

### 4.1 AWS Deferred Tasks

- [ ] CloudWatch dashboard — key metrics for all 6 services
- [ ] CloudWatch alarms — error rates, latency, task failures
- [ ] Scale up worker ECS services (currently `desired=0`)
- [ ] CI/CD IAM role (replace personal access key)

### 4.2 Secrets & Config

- [ ] Replace OpenAI API key placeholder in Secrets Manager
- [ ] Add YouTube Data API key to Secrets Manager
- [ ] Add other API keys (Deepgram, data providers)
- [ ] Wire ECS task definitions to pull secrets from Secrets Manager

### 4.3 Observability

- [ ] Structured logging across all services
- [ ] Health check endpoints that verify DB connectivity
- [ ] Request tracing (correlation IDs)
- [ ] Metrics: ingestion rate, extraction accuracy, decision cadence

### 4.4 Data Sources

- [ ] Curate initial list of 50+ NRL SuperCoach content sources
- [ ] Categorise by type (YouTube, podcast, web, radio)
- [ ] Seed the `sources` table with approved sources
- [ ] Identify match results data source (official NRL API, web scraping, etc.)

---

## Phase 5 — Polish & Launch

### 5.1 Testing

- [ ] Unit tests for extraction logic
- [ ] Unit tests for decision engine heuristics
- [ ] Integration tests for ingestion → extraction → consensus pipeline
- [ ] End-to-end test: source ingestion to published feed event
- [ ] Load testing for API endpoints

### 5.2 Security

- [ ] Review CORS settings (currently `allow_origins=["*"]`)
- [ ] Add API authentication
- [ ] Input validation on all endpoints
- [ ] Rate limiting
- [ ] Content Security Policy headers

### 5.3 Launch Prep

- [ ] Custom favicon and OpenGraph images
- [ ] Social media preview cards (Twitter/X, Facebook)
- [ ] Analytics (Plausible, Umami, or similar)
- [ ] Error tracking (Sentry or similar)
- [ ] Backup strategy for RDS
- [ ] Domain email setup (optional)

---

## Suggested Build Order

| Priority | Task | Why |
|----------|------|-----|
| 1 | Temporal setup | Orchestrates everything |
| 2 | DB models + shared module | Foundation for all services |
| 3 | Ingestion worker (YouTube first) | Data in = everything else possible |
| 4 | Extraction worker | Turns raw text into structured knowledge |
| 5 | Consensus engine | Aggregates opinions for decisions |
| 6 | API feed endpoint + Feed UI | First public-facing feature |
| 7 | Decision worker | Jaromelu starts making moves |
| 8 | Publishing worker + voice | Jaromelu gets personality |
| 9 | Remaining API endpoints + pages | Full experience |
| 10 | Admin interface | Operator control |
