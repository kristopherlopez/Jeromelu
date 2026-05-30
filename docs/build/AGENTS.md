# Build Docs Instructions

Read this before editing `docs/build/**`.

## Scope

Build docs coordinate Codex goals, work orders, live threads, process invariants, and durable run reports.

## Required Context

- Process rules: `docs/build/META.md`
- Active plans: `docs/build/PLAN.md`
- Dispatchable work: `docs/build/WORK_ORDERS.md`
- Live thread state: `docs/build/THREADS.md`
- Run report index: `docs/build/runs/README.md`

## Rules

- `META.md` is for durable process rules and project invariants.
- `PLAN.md`, `WORK_ORDERS.md`, and `THREADS.md` hold active/future state only.
- `TASKS.md` is legacy compatibility only. Do not add new tasks there.
- Run reports are the durable history. Create or update them as part of goal completion.
- When a work order is integrated, record proof in the run report, remove it from `WORK_ORDERS.md`, and clear/archive the thread row.
- Keep work orders dispatchable: explicit `Depends-on`, `Touches`, owner branch, and verification.
