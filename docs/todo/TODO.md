# Jaromelu — Master To-Do

Component-level work has its own file under `docs/todo/`. Cross-cutting items (infra, testing, security, launch prep) stay inline below.

---

## Phase 1 — Prove the Brain (Intelligence Layer)

- **1.1 Temporal Orchestration Setup** → [temporal-orchestration.md](temporal-orchestration.md)
- **1.2 Ingestion Worker** → [ingestion-worker.md](ingestion-worker.md)
- **1.3 Extraction Worker** → [extraction-worker.md](extraction-worker.md)
- **1.4 Consensus Engine** → [consensus-engine.md](consensus-engine.md)

### 1.5 Database Layer

- [x] SQLAlchemy ORM models for all 12 tables — `packages/shared/jeromelu_shared/db/models.py`
- [x] Shared database module — `packages/shared/` pip-installable package
- [x] Connection pooling and session management — `packages/shared/jeromelu_shared/db/session.py`
- [ ] Alembic migration runner for future schema changes

---

## Phase 2 — Prove the Character (Personality + Experience)

- **2.1 Decision Worker** → [decision-worker.md](decision-worker.md)
- **2.2 Publishing Worker** → [publishing-worker.md](publishing-worker.md)
- **2.3 Match Review System** → [match-review.md](match-review.md)

---

## Phase 3 — API & Frontend

- **3.1 API Endpoints** → [api.md](api.md)
- **3.3 Admin Interface** → [admin-interface.md](admin-interface.md)

### 3.2 Frontend Pages (`services/web`)

- [x] **The Feed** — live event stream (core product surface), `/`
- [x] **The Wiki** — agent-maintained knowledge base, `/wiki`
- [x] **The Ledger** — prediction tracking, `/ledger`
- [x] **The Analysis** — editorial articles, `/insights`
- [x] **Ask Me** — merged into Feed as Twitch-style chat; Q&A persisted as feed events with temperature control
- [ ] Responsive design / mobile-friendly pass across all pages
- [ ] SEO metadata for public pages

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
