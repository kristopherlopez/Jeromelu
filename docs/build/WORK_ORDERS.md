# Jaromelu Work Orders

Dispatchable work for the current Codex goal. The coordinator owns this file and uses it to decide which worker, reviewer, and tester threads can run in parallel.

## Format

Each work order is a level-3 heading with labelled fields:

- **Plan.** Link to the `PLAN.md` section that defines the goal and interface.
- **State.** `ready`, `in-flight`, `review`, `[BLOCKED: reason]`, or `done-pending-report`.
- **Owner.** Thread ID and role once dispatched; `unassigned` before dispatch.
- **Branch.** Worker branch/worktree, usually `codex/<goal>-<slice>`; `none` for read-only/operator work.
- **Depends-on.** Work order IDs that must be integrated before this one starts, or `none`.
- **Touches.** Repo paths/globs this work order may create or modify, or `none` for read-only/operator work.
- **What.** Exactly what to do. The worker should not redesign this.
- **How to verify.** Concrete commands, API checks, screenshots, or queries with expected output.
- **Proof notes.** In-flight scratchpad only. The durable proof goes in the active run report after review/test passes.

## Dispatch Rules

- The coordinator may run two work orders concurrently only when their `Touches` sets are disjoint and neither depends on the other.
- A worker owns only its assigned work order and branch. It must not pick more work from this file.
- Reviewer and tester threads read the assigned work order, plan section, and relevant proof. They do not edit unless the coordinator explicitly converts the follow-up into a worker assignment.
- Finished work orders are recorded in the active run report, then removed from this file. This file holds live/future work only.
- Blocked work orders stay here with `[BLOCKED: reason]` until the coordinator or human resolves them.

## Tags

Prefix the title with optional tags in square brackets:

- `[P0]`, `[P1]`, `[P2]`, `[P3]` - severity from `issue-triager`.
- `[BLOCKED: reason]` - cannot proceed without coordinator or human input.

---

## Open work orders

No open work orders.

---

## Completed work

Completed work is not kept here. When a work order passes review/test and is integrated, what it delivered is recorded in the active run report under [`docs/build/runs/`](./runs/) and the work order is removed from this file.
