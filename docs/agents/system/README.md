---
tags: [area/agents, subarea/system]
---

# System Agents

Backend workers. Temporal workflows, LLM activities, and scrapers that actually run.

All Temporal agents share infrastructure defined in `packages/shared/jeromelu_shared/temporal.py` — task queue constants, client factory, deterministic workflow ID generation.

See also: [`../../architecture/02-runtime-architecture.md`](../../architecture/02-runtime-architecture.md), [`../../architecture/03-llm-architecture.md`](../../architecture/03-llm-architecture.md), [`../../architecture/04-workflow-architecture.md`](../../architecture/04-workflow-architecture.md).

---

## Agents

| Worker / Agent | Status | Task Queue | Schedule |
|----------------|--------|------------|----------|
| [Orchestrator](orchestrator.md) | Skeleton | `orchestrator` | N/A |
| [Ingestion](ingestion.md) | Live | `ingestion` | Daily 10 PM AEST |
| [Publishing](publishing.md) | Live | `publishing` | On-demand |
| [Scraper](scraper.md) | Partial | `scraper` | Mon/Wed/Thu AEST |
| [Extraction](extraction.md) | Not yet built | `extraction` | — |
| [Decision](decision.md) | Not yet built | `decision` | — |

---

## Topology

```
Temporal Server
├── worker-orchestrator (orchestrator)
│   └── (workflow definitions — intended hub, currently empty)
│
├── worker-ingestion (ingestion)
│   └── IntelSweepWorkflow
│       ├── discover_new_videos
│       ├── collect_transcript
│       └── index_document
│
├── worker-publishing (publishing)
│   ├── FeedGenerationWorkflow
│   └── KBGenerationWorkflow
│
├── worker-scraper (scraper) — RETIRED 2026-05-28 (Scout Phase 4 closure;
│                                migrated to services/api/app/scout/<pipeline>/)
│
├── worker-extraction (extraction) — NOT YET BUILT
└── worker-decision (decision) — NOT YET BUILT
```
