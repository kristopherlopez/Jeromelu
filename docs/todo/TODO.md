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

V1 architecture is single-instance Lightsail + Docker Compose. See `docs/architecture/12-aws-architecture.md` and Phase 11 of `docs/operations/aws-resource-inventory.md` for live state.

### 4.1 Lightsail V1 Cutover

V0 → V1 migration. Stack files (`docker-compose.prod.yml`, `Caddyfile`, `lightsail-deploy.sh`, `pg-backup.sh`, `.github/workflows/deploy.yml`, Makefile prod targets) committed in Phase 0.

- [x] **Phase 1**: Provision Lightsail instance `jeromelu` (`micro_3_2` $7/mo — Sydney has no $5 plan with 1 GB RAM; ap-southeast-2a, Ubuntu 22.04)
- [x] **Phase 1**: Attach static IP `52.65.91.199`; firewall TCP 22 from `112.213.139.221/32`, 80/443 from `0.0.0.0/0`
- [x] **Phase 1**: Bootstrap (Docker 29.4.1, Compose, AWS CLI v2, Git, 1 GB swap)
- [x] **Phase 2**: Final RDS snapshot `jeromelu-db-pre-lightsail-2026-04-25` (available, retain until 2026-05-25)
- [x] **Phase 2**: pg_dump from RDS → restore into Postgres container on Lightsail; row counts match (sources=215, source_documents=215, source_chunks=221,634)
- [x] **Phase 3**: IAM user `jeromelu-cicd` (GH Actions: ECR + CloudFront invalidate); GitHub Actions secrets set
- [x] **Phase 3**: IAM user `jeromelu-instance` (Lightsail box: ECR pull, S3, SSM); keys in `/opt/jeromelu/.env` and `~/.aws/credentials`
- [x] **Phase 3**: 6 SecureStrings in Parameter Store under `/jeromelu/`: `postgres-password`, `openai-api-key` (still placeholder), `admin-key`, `session-secret`, instance AWS keypair
- [x] **Phase 3**: GitHub deploy key registered for read-only repo access from Lightsail
- [x] **Phase 3**: Repo cloned to `/opt/jeromelu` via SSH
- [ ] **Phase 4**: Run `scripts/lightsail-deploy.sh` — Caddy + web + api + postgres on the box
- [ ] **Phase 5**: Repoint CloudFront `E2G6FL11A3JP8F` origin from ALB DNS to Lightsail static IP
- [ ] **Phase 5**: Repoint Route 53 `api.jeromelu.ai` A record to Lightsail static IP
- [ ] **Phase 7**: Verify nightly `pg-backup.sh` cron lands in `s3://jeromelu-public-assets/backups/postgres/` and test full restore

### 4.2 V0 Decommissioning

Delete only after V1 is verified live for 24–48h. Resources flagged DECOMMISSIONED in `aws-resource-inventory.md`.

- [ ] Delete ECS services, cluster, ALB, target groups
- [ ] Delete RDS instance `jeromelu-db` (final snapshot retained 30 days)
- [ ] Delete NAT Gateway `nat-0ebe6638ebe58e8ce`, release the Elastic IP
- [ ] Delete Secrets Manager entries (replaced by Parameter Store, ~$1.20/mo saved)
- [ ] Schedule KMS key `jeromelu-master-key` deletion (7-day waiting period)
- [ ] Delete unused `ap-southeast-2` ACM cert (was the ALB cert)
- [ ] Prune unused `worker-*` ECR repos (deferred per architecture doc — fine for now)

### 4.3 Secrets & Config

- [ ] Replace OpenAI API key placeholder in Parameter Store (`/jeromelu/openai-api-key`)
- [ ] Add YouTube Data API key to Parameter Store
- [ ] Add other API keys (Deepgram, data providers) to Parameter Store
- [ ] Verify `aws ssm get-parameters-by-path /jeromelu/` populates `/opt/jeromelu/.env` on deploy

### 4.4 Observability

V1 deliberately skips CloudWatch agent + alarms — rely on Lightsail's instance metrics dashboard and `journald`. App-level instrumentation is still wanted.

- [ ] Structured logging across all services (JSON → stdout → `journald`, tail via `make prod-logs`)
- [ ] Health check endpoints that verify DB connectivity
- [ ] Request tracing (correlation IDs)
- [ ] Metrics: ingestion rate, extraction accuracy, decision cadence

### 4.5 Data Sources

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
