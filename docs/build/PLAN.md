# Jaromelu Build Plan

This document holds active and historical plan docs that drive the persistent task queue in [TASKS.md](./TASKS.md). Plans are written by the `planner` agent (or a planning session) and consumed by the `implementer`.

## What good looks like

A good plan doc is:

- **Self-contained** — readable cold by an implementer with no prior conversation context.
- **Interface-level** — names file paths, types, function signatures, table columns, API shapes, env vars. No "figure out the right shape".
- **End-to-end verifiable** — explicit "how do we know this is done" strategy, runnable from the outside (curl, CLI, screenshot, query).
- **Iterated to high quality** before any task is appended. A plan that ships fuzzy tasks burns implementer time on re-asking.

Plans link to the tasks they spawn. Tasks link back to the plan section they implement.

---

## Active plan

_No active plan. Last shipped initiative: [Scout Phase 4 — nrl.com casualty ward + ladder + retire worker-scraper (2026-05-28)](./runs/2026-05-28-scout-phase-4-casualty-ladder.md)._


## Completed work

Completed plans are **not** archived in this file. When a plan's tasks are all done, its durable record is a run report under [`docs/build/runs/`](./runs/) (see the [index](./runs/README.md)) and the plan is removed from "Active plan" above. This document holds only active/future plans; the run reports are the system of record for what shipped.
