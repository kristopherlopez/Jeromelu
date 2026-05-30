# Jaromelu Build Plan

This document holds active Codex goal plans that drive dispatchable work orders in [WORK_ORDERS.md](./WORK_ORDERS.md). Plans are written by the `planner` agent or a coordinator planning session, then consumed by coordinator, worker, reviewer, and tester threads.

## What good looks like

A good plan doc is:

- **Self-contained** — readable cold by a worker with no prior conversation context.
- **Interface-level** — names file paths, types, function signatures, table columns, API shapes, env vars. No "figure out the right shape".
- **End-to-end verifiable** — explicit "how do we know this is done" strategy, runnable from the outside (curl, CLI, screenshot, query).
- **Dispatchable** — names dependency boundaries and safe `Touches` sets so independent slices can run in separate Codex worktree threads without collisions.
- **Iterated to high quality** before any work order is appended. A plan that ships fuzzy work orders burns worker time on re-asking.

Plans link to the work orders they spawn. Work orders link back to the plan section they implement.

---

## Active plan

No active plan.

## Completed work

Completed plans are **not** archived in this file. When a plan's work orders are all done, its durable record is a run report under [`docs/build/runs/`](./runs/) (see the [index](./runs/README.md)) and the plan is removed from "Active plan" above. This document holds only active/future plans; the run reports are the system of record for what shipped.
