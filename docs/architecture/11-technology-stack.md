---
tags: [area/architecture]
---

# Recommended Technology Stack

## Frontend
- **Next.js + TypeScript**
- Tailwind CSS
- server-rendered pages for SEO
- dynamic modules for feed, dashboard, explorer, and chat

## Public / Admin API
- **FastAPI + Python**
- Pydantic for typed schemas
- SSE or WebSockets only where near-real-time updates matter

## Workflow Orchestration
- **Temporal**
- separate worker processes for ingestion, extraction, decisioning, and publishing

## Data Layer
- **PostgreSQL** as the system of record
- **pgvector** inside PostgreSQL for embeddings and semantic retrieval
- PostgreSQL full-text search for lexical retrieval
- S3-compatible object storage for raw transcripts and artefacts

## AI Layer
- OpenAI API for:
  - extraction
  - synthesis
  - character rendering
  - embeddings

## Runtime / Infra
- Dockerised services
- managed PostgreSQL
- object storage
- Temporal workers as separate services

## Observability
- structured logs
- tracing
- error monitoring
- Postgres-backed audit tables for operator actions

## Recommended Service Split
- `web` — Next.js public experience
- `api` — FastAPI experience backend
- `worker-ingestion` — source discovery and ingestion
- `worker-extraction` — entities, quotes, claims, predictions, embeddings
- `worker-decision` — consensus, planning, decisioning
- `worker-publishing` — feed events, voice rendering, public state updates
- `worker-scraper` — SuperCoach stats, prices, team lists
- `temporal` — orchestration layer
- `postgres` — core data store
- `object-store` — transcript and artefact storage

For what each worker actually does today (including status and workflow inventory), see [`docs/agents/system/`](../agents/system/README.md).

## Key Technical Principle
Keep the **public experience** and the **intelligence engine** separate, but keep the **data layer unified**.
