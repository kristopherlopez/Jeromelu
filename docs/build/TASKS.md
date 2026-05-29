# Jaromelu Task Queue

Persistent queue for the long-lived implementer session. The implementer reads top-down, completes one task at a time, dispatches `adversarial-reviewer` against the diff + task + plan, and only checks off after the review passes.

## Format

Each task is a level-3 heading with three labelled blocks (plus optional scheduling metadata, below):

- **What** — exactly what to do. References a section of `PLAN.md`.
- **How to verify** — concrete checks. Commands, files, expected output. Bar: "if satisfied exactly as written, the result is trustworthy."
- **Proof notes** — an optional in-flight scratchpad only. The **authoritative** proof record is the task's entry in the active run report under [`docs/build/runs/`](./runs/), written **at checkoff (after the review passes)**.

**Proof timing (important for reviewers):** under the run-report ritual, proof is recorded into the run report *at checkoff*, which is downstream of the review. So an **empty Proof-notes block at review time is expected and is NOT a blocker** — the reviewer verifies the diff against the spec and runs the **How to verify** checks itself; proof recording is a post-pass step.

Mark as `[x]` only after `adversarial-reviewer` passes. Once it passes, record what the task delivered in the active run report under [`docs/build/runs/`](./runs/) and **remove it from this file** — TASKS.md holds only the live queue, not a completed-task graveyard (see the run-report ritual in [META.md](./META.md)).

### Scheduling metadata (optional)

Two optional one-line fields at the **top** of a task, before **What**, let the implementer (and, later, a worktree dispatcher) decide ordering and safe concurrency. Both are written by the `planner`. Omit a field only when the answer is genuinely "none".

- **Depends-on.** Task IDs that must be checked off (and thus removed from the queue) before this task can start — e.g. `TASK-45`, or `none`. The implementer never picks a task whose dependencies are still open; it skips to the next eligible task rather than treating queue order alone as the gate.
- **Touches.** The repo paths/globs this task will create or modify — e.g. `services/api/app/scout/**`, `scripts/data/populate/phase_matches.py`. An operator-only task that changes no repo files declares `none`. **The concurrency contract:** two tasks may run at the same time only when their **Touches** sets are disjoint *and* neither **Depends-on** the other. For the single-implementer loop today this is documentation plus a smarter pick rule; it's the precondition a fan-out dispatcher relies on, so declare it honestly even while execution is serial.

### Tags

Prefix the title with optional tags in square brackets:

- `[P0]`, `[P1]`, `[P2]`, `[P3]` — severity (from `issue-triager`)
- `[BLOCKED: reason]` — implementer hit a wall; needs human input

---

## Open tasks

_Queue is empty. The most recent plan, [Scout Phase 5 — Historical backfill + standard-data-model conformance](./runs/2026-05-28-scout-phase-5-historical-backfill.md), shipped 2026-05-29. Awaiting the next plan._

---

## Completed work

Completed tasks are not kept here. When a task passes review and is checked off, what it delivered is recorded in the active run report under [`docs/build/runs/`](./runs/) and the task is removed from this file. This queue holds only open/in-flight work.
