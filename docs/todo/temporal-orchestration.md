---
tags: [area/todo, status/planning]
---

# 1.1 Temporal Orchestration Setup

**Phase:** 1 — Prove the Brain (Intelligence Layer)
**Priority:** 1 — Orchestrates everything

## Architecture Decisions

### Worker Pattern: Dedicated Orchestrator (Pattern B)
- A dedicated `worker-orchestrator` service owns all **workflow definitions**
- The 4 activity workers (ingestion, extraction, decision, publishing) register only **activities**, never workflows
- Workflows in the orchestrator dispatch activities to the specialized workers' task queues
- Clean separation of "what to do" (orchestrator) from "how to do it" (activity workers)

### Task Queues

| Task Queue | Owner | Purpose |
|---|---|---|
| `orchestrator` | worker-orchestrator | Workflow definitions |
| `ingestion` | worker-ingestion | Ingest/scrape/transcribe activities |
| `extraction` | worker-extraction | Entity/quote/claim extraction activities |
| `decision` | worker-decision | Scoring, ranking, strategy activities |
| `publishing` | worker-publishing | Feed events, voice rendering activities |

### Shared Temporal Module
`jeromelu_shared/temporal.py` — follows the established pattern alongside `db/`, `s3.py`, `llm.py`:
- `get_temporal_client()` — async client factory, reads host/namespace from `Settings`
- Task queue name constants (`ORCHESTRATOR_QUEUE`, `INGESTION_QUEUE`, etc.)
- Workflow ID helpers — deterministic, readable IDs (e.g., `daily-intel-sweep-2026-03-09`)

### Workflow Triggering
- **Temporal schedules** for recurring workflows (daily intel sweep, weekly decisions, etc.)
- **API service** starts workflows on-demand via Temporal client SDK (operator triggers, breaking news, etc.)

## Tasks

- [x] Deploy Temporal server (docker-compose) — added to docker-compose.yml
- [x] Configure Temporal namespace — added `TEMPORAL_NAMESPACE: jeromelu` env var to temporal service in docker-compose
- [x] Create `worker-orchestrator` service — Dockerfile, `main.py`, connects to Temporal, registers on `orchestrator` task queue
- [x] Update `worker-ingestion` to connect to Temporal and register on `ingestion` task queue
- [x] Update `worker-extraction` to connect to Temporal and register on `extraction` task queue
- [x] Update `worker-decision` to connect to Temporal and register on `decision` task queue
- [x] Update `worker-publishing` to connect to Temporal and register on `publishing` task queue
- [x] Create `jeromelu_shared/temporal.py` — client factory, task queue constants, workflow ID helpers
- [x] Add API helper for starting workflows on-demand — `temporalio` added to API deps, client available via `jeromelu_shared.temporal`

## Deferred

- **Workflow definitions** in the orchestrator — circle back after activity workers are built (depends on 1.2, 1.3, 2.1, 2.2)
- **Temporal schedule registration** — requires workflow definitions first
- **Activity interfaces and implementations** — defined with each worker (1.2, 1.3, 2.1, 2.2)
- **Retry/timeout policies per activity** — defined with each worker (see 1.2, 1.3, 2.1, 2.2)

## Notes

- Namespace retention: 7 days local dev, 30 days production
- Skip archival and custom search attributes until needed at scale
