# Jeromelu — Master To-Do Index

## Phase 1 — Prove the Brain (Intelligence Layer)
- [1_1_temporal_orchestration_setup.md](1_1_temporal_orchestration_setup.md) — Temporal server, namespace, worker registration
- [1_2_ingestion_worker.md](1_2_ingestion_worker.md) — YouTube, web, podcast ingestion pipeline
- [1_3_extraction_worker.md](1_3_extraction_worker.md) — Entity, quote, claim, prediction extraction
- [1_4_consensus_engine.md](1_4_consensus_engine.md) — Consensus snapshots, contrarian scores
- [1_5_database_layer.md](1_5_database_layer.md) — ORM models, shared package, Alembic

## Phase 2 — Prove the Character (Personality + Experience)
- [2_1_decision_worker.md](2_1_decision_worker.md) — Rule-based decisions, squad management
- [2_2_publishing_worker.md](2_2_publishing_worker.md) — Feed events, Jerome's voice
- [2_3_match_review_system.md](2_3_match_review_system.md) — Outcomes, accuracy tracking

## Phase 3 — API & Frontend
- [3_1_api_endpoints.md](3_1_api_endpoints.md) — FastAPI routes, auth, rate limiting
- [3_2_frontend_pages.md](3_2_frontend_pages.md) — Live Feed, War Room, dashboards
- [3_3_admin_interface.md](3_3_admin_interface.md) — Source approval, kill switch, entity tools

## Phase 4 — Infrastructure & Operations
- [4_1_aws_deferred_tasks.md](4_1_aws_deferred_tasks.md) — CloudWatch, ECS scaling, IAM
- [4_2_secrets_and_config.md](4_2_secrets_and_config.md) — API keys, Secrets Manager
- [4_3_observability.md](4_3_observability.md) — Logging, tracing, health checks
- [4_4_data_sources.md](4_4_data_sources.md) — Source curation, match results data

## Phase 5 — Polish & Launch
- [5_1_testing.md](5_1_testing.md) — Unit, integration, E2E, load tests
- [5_2_security.md](5_2_security.md) — CORS, auth, CSP headers
- [5_3_launch_prep.md](5_3_launch_prep.md) — Branding, analytics, error tracking

---

## Suggested Build Order

| Priority | Task | Why |
|----------|------|-----|
| 1 | Temporal setup | Orchestrates everything |
| 2 | DB models + shared module | Foundation for all services |
| 3 | Ingestion worker (YouTube first) | Data in = everything else possible |
| 4 | Extraction worker | Turns raw text into structured knowledge |
| 5 | Consensus engine | Aggregates opinions for decisions |
| 6 | API feed endpoint + Live Feed UI | First public-facing feature |
| 7 | Decision worker | Jerome starts making moves |
| 8 | Publishing worker + voice | Jerome gets personality |
| 9 | Remaining API endpoints + pages | Full experience |
| 10 | Admin interface | Operator control |

---

## What's Already Built
- Database schema deployed (12 tables, 21 indexes) — `packages/db/migrations/001_initial_schema.sql`
- SQLAlchemy ORM models — `packages/shared/jeromelu_shared/db/models.py`
- Shared Python package (config, DB session, S3 helpers, LLM helpers) — `packages/shared/`
- Docker Compose (Postgres + pgvector, MinIO, Temporal, Temporal UI) — `docker/docker-compose.yml`
- CI/CD pipeline (GitHub Actions, per-service Docker builds) — `.github/workflows/deploy.yml`
- Next.js landing page — `services/web/`
- FastAPI health check — `services/api/`
- All service Dockerfiles updated for shared package
