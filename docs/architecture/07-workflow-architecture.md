---
tags: [area/architecture]
---

# Workflow Architecture

> **Status (2026-05-23): intent sketch — not the system that runs today.** There is no workflow engine in production. Temporal is local-dev only (see [11-technology-stack](11-technology-stack.md)); the decision and extraction workers aren't built. What actually runs is **cron jobs** (`scripts/cron.d/jeromelu`) and one-shot CLI invocations. For what's built and which worker owns it, see [`docs/agents/system/`](../agents/system/README.md) and the layer map in [05-runtime-architecture](05-runtime-architecture.md).

The intended workflow shapes, once the pipeline supports them:

- **Daily intel sweep** — Scout ingests approved sources; Analyst extracts claims/predictions; consensus refreshes; notable Feed events publish.
- **Match review** — collect outcomes, grade against predictions, publish hits/misses, update the Alignment Index.
- **Continuous wiki maintenance** — the Archivist updates affected pages whenever upstream data lands (async, no weekly climax).
- **Event-triggered re-evaluation** — breaking injury news, late team changes, an urgent source claim, or an operator event trigger partial re-evaluation. This is the engine behind the live-number heartbeat in [02 — The Show](../vision/02-the-show.md).

> SuperCoach-specific flows (squad / team-state decisions) belong to the deferred V2 overlay, not V1 NRL commentary.
