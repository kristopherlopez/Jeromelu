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

### 2026-05-30 - Scout roadmap completion

**Objective.** Close the implementable Scout roadmap gaps that remain after Phase 5, using disjoint worker branches/worktrees and read-only review before coordinator integration.

**Source.** [`docs/agents/crew/scout/roadmap.md`](../agents/crew/scout/roadmap.md), especially Phase 6 and the YouTube-depth backlog rows.

**Dependency graph.**

| Slice | Depends on | Notes |
|---|---|---|
| SCOUT-OPS-SCHEDULES | none | Cron/wrapper/docs only. Independent. |
| SCOUT-YT-AGENT-RUNS | none | Adds deterministic YouTube/recon audit rows. Unblocks dashboard and source health. |
| SCOUT-RECON-UI | none | Admin review queue UI. Independent, but later dashboard web work must merge around `AdminClient.tsx`. |
| SCOUT-MEDIA-DRAIN | none | Recurring drain CLI/job surface. Independent. |
| SCOUT-DETERMINISTIC-YT | none | Deterministic discovery surface. Unblocks source-discovery scheduling. |
| SCOUT-DASHBOARD-API | SCOUT-YT-AGENT-RUNS | Reads `agent_runs` by Scout pipeline. |
| SCOUT-DASHBOARD-WEB | SCOUT-DASHBOARD-API, SCOUT-RECON-UI | Adds `/admin/scout` or admin tab UI after API shape lands. |
| SCOUT-SOURCE-DISCOVERY-SCHED | SCOUT-DETERMINISTIC-YT | Cron/APScheduler wrapper for deterministic discovery. |
| SCOUT-SOURCE-HEALTH | SCOUT-YT-AGENT-RUNS | Liveness/stalled-channel checks need audit/run semantics. |

**Parallelism rule.** Run all first-wave branches in parallel because their code touches are disjoint, then review them in parallel. Start second-wave workers only after their dependency branches pass review or are integrated. Keep dashboard API and dashboard web sequential because the web depends on API response shape and overlaps the admin UI area touched by recon.

**Verification strategy.**

- Python unit tests for changed API/Scout modules.
- Typecheck/lint for web changes.
- CLI `--help` and dry-run checks for schedulers/drain/discovery commands.
- Read-only adversarial review per worker branch before integration.
- Final coordinator verification from a clean integration worktree before landing.

## Completed work

Completed plans are **not** archived in this file. When a plan's work orders are all done, its durable record is a run report under [`docs/build/runs/`](./runs/) (see the [index](./runs/README.md)) and the plan is removed from "Active plan" above. This document holds only active/future plans; the run reports are the system of record for what shipped.
