---
tags: [area/archive, status/archived]
---

# Jaromelu — What's Built (archived snapshot, superseded)

> **Archived 2026-04-17.** This was a point-in-time snapshot. It is out of date (e.g., "Next.js placeholder landing page" no longer applies — the app now has five live pages). Kept only for historical reference. For current implementation status, read the code; for planned work, see [todo/TODO.md](../todo/TODO.md).

---

## Infrastructure
- Monorepo structure with 6 services
- Docker Compose local dev (Postgres + pgvector, MinIO, Temporal, Temporal UI) — `docker/docker-compose.yml`
- CI/CD pipeline (GitHub Actions, per-service Docker builds) — `.github/workflows/deploy.yml`
- All service Dockerfiles updated for shared package

## Database
- Schema deployed (12 tables, 21 indexes) — `packages/db/migrations/001_initial_schema.sql`
- SQLAlchemy ORM models — `packages/shared/jeromelu_shared/db/models.py`
- `s3_key` column on `source_documents` for transcript storage tracking

## Shared Package (`packages/shared/`)
- Config (pydantic-settings, psycopg driver)
- DB session management
- S3 helpers
- LLM helpers

## Ingestion Worker (`services/worker-ingestion/`)
- Temporal workflow: `IntelSweepWorkflow`
- Discovery activity — RSS feed polling, watermark + checksum dedup
- Collection activity — `youtube-transcript-api` transcripts, S3 storage
- Processing activity — plain text extraction from JSON segments
- Indexing activity — write `source` and `source_document` records to DB
- Backfill script for bulk transcript ingestion — `services/worker-ingestion/app/backfill.py`

## Web (`services/web/`)
- Next.js placeholder landing page

## API (`services/api/`)
- FastAPI health check endpoint
