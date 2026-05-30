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

### SCOUT-OPS-SCHEDULES

- **Plan.** [Scout roadmap completion](./PLAN.md#2026-05-30---scout-roadmap-completion)
- **State.** review
- **Owner.** worker branch complete; reviewer `019e76a3-9821-7d50-8c21-d1b768e3afe4`
- **Branch.** `codex/scout-roadmap-ops-sched` / `C:\tmp\Jeromelu-ops-sched`
- **Depends-on.** none
- **Touches.** `scripts/scout-refresh.sh`, `scripts/scout-populate.sh`, `scripts/cron.d/jeromelu`, `scripts/data/populate/README.md`, related Scout/ops docs
- **What.** Add missing operator scheduling/wrapper coverage for shipped deterministic Scout pipelines and document the prod/runtime expectations.
- **How to verify.** Shell syntax checks, wrapper dry-runs, cron shape checks, docs review.
- **Proof notes.** Worker commit `fa75243048ce799694ef585e9b4c2a17f5126540` pushed; parallel review in progress.

### SCOUT-YT-AGENT-RUNS

- **Plan.** [Scout roadmap completion](./PLAN.md#2026-05-30---scout-roadmap-completion)
- **State.** review
- **Owner.** worker branch complete; reviewer `019e76a3-ca9f-76d3-875d-b1a7068a48db`
- **Branch.** `codex/scout-roadmap-yt-agent-runs` / `C:\tmp\Jeromelu-scout-yt-agent-runs`
- **Depends-on.** none
- **Touches.** `services/api/app/scout/youtube/refresh.py`, `services/api/app/routers/recon.py`, `tests/unit/api/scout/test_youtube_refresh_audit.py`, data-lineage docs
- **What.** Standardise deterministic YouTube/recon jobs onto `agent_runs` so downstream health/dashboard work has a durable run source.
- **How to verify.** Unit tests for audit rows, import checks, docs review.
- **Proof notes.** Worker commit `a600862d72c6dae5189822295ea347b5283a789b` pushed; pytest reached 100% but local environment timed out during shutdown; parallel review in progress.

### SCOUT-RECON-UI

- **Plan.** [Scout roadmap completion](./PLAN.md#2026-05-30---scout-roadmap-completion)
- **State.** review
- **Owner.** worker branch complete; reviewer `019e76a3-fc73-77c0-8133-7561ffd733d5`
- **Branch.** `codex/scout-roadmap-recon-ui` / `C:\tmp\Jeromelu-recon-ui`
- **Depends-on.** none
- **Touches.** `services/web/src/app/admin/AdminClient.tsx`, `services/web/src/app/admin/ReconCandidatesPanel.tsx`
- **What.** Add the admin recon candidate review queue UI.
- **How to verify.** Web lint/typecheck and reviewer inspection for admin UI regressions.
- **Proof notes.** Worker commit `84d4b02356e62fdcc4f4d23af9fca341a53aa5be` pushed; lint/typecheck passed with existing warnings; parallel review in progress.

### SCOUT-MEDIA-DRAIN

- **Plan.** [Scout roadmap completion](./PLAN.md#2026-05-30---scout-roadmap-completion)
- **State.** review
- **Owner.** worker branch complete; reviewer `019e76a4-2fa7-7990-9765-bb25971b3f16`
- **Branch.** `codex/scout-roadmap-media-drain-v2` / `C:\tmp\Jeromelu-media-drain`
- **Depends-on.** none
- **Touches.** `services/api/app/scout/media/drain.py`, `services/api/app/scout/media/cli/drain_audio.py`, `services/api/app/analyst/transcribe_drain_cli.py`, drain tests, `Makefile`, ingestion/transcription docs
- **What.** Add a reusable recurring drain surface for pending media ingestion/transcription work.
- **How to verify.** CLI help checks, drain unit tests, docs review.
- **Proof notes.** Worker commit `9017ec1deb414f2e3b7cf6016effae43f480f35e` pushed; pytest reached 100% but local environment timed out during shutdown; parallel review in progress.

### SCOUT-DETERMINISTIC-YT

- **Plan.** [Scout roadmap completion](./PLAN.md#2026-05-30---scout-roadmap-completion)
- **State.** review
- **Owner.** worker branch complete; reviewer `019e76a4-6590-7a60-89dc-63df55c90898`
- **Branch.** `codex/scout-roadmap-deterministic-yt` / `C:\tmp\Jeromelu-deterministic-yt`
- **Depends-on.** none
- **Touches.** `services/api/app/scout/source_discovery/**`, `services/api/app/scout/routes.py`, Scout/source-discovery docs, deterministic-discovery tests
- **What.** Land the deterministic YouTube discovery surface from the Scout architecture plan.
- **How to verify.** Unit tests for filtering/scoring/persistence, CLI help, route import checks.
- **Proof notes.** Worker commit `d374dc3695db8ede9358f4e6e1751e87713944cf` pushed; pytest passed its collected tests but local environment timed out during shutdown; parallel review in progress.

### SCOUT-DASHBOARD-API

- **Plan.** [Scout roadmap completion](./PLAN.md#2026-05-30---scout-roadmap-completion)
- **State.** ready
- **Owner.** unassigned
- **Branch.** `codex/scout-roadmap-dashboard-api`
- **Depends-on.** SCOUT-YT-AGENT-RUNS
- **Touches.** `services/api/app/routers/**`, Scout dashboard API tests, dashboard docs
- **What.** Expose a Scout pipeline health endpoint backed by `agent_runs`, grouped by `detail_json.pipeline`.
- **How to verify.** Unit tests for grouping/status/row-count response shape and import/API checks.
- **Proof notes.** Waiting for SCOUT-YT-AGENT-RUNS review/integration.

### SCOUT-DASHBOARD-WEB

- **Plan.** [Scout roadmap completion](./PLAN.md#2026-05-30---scout-roadmap-completion)
- **State.** ready
- **Owner.** unassigned
- **Branch.** `codex/scout-roadmap-dashboard-web`
- **Depends-on.** SCOUT-DASHBOARD-API, SCOUT-RECON-UI
- **Touches.** `services/web/src/app/admin/**`
- **What.** Add the operator Scout dashboard UI after the API response shape is stable.
- **How to verify.** Web typecheck/lint and browser/UI smoke check.
- **Proof notes.** Sequential behind API and recon UI to avoid admin-surface conflicts.

### SCOUT-SOURCE-DISCOVERY-SCHED

- **Plan.** [Scout roadmap completion](./PLAN.md#2026-05-30---scout-roadmap-completion)
- **State.** ready
- **Owner.** unassigned
- **Branch.** `codex/scout-roadmap-source-discovery-sched`
- **Depends-on.** SCOUT-DETERMINISTIC-YT
- **Touches.** `scripts/scout-refresh.sh`, `scripts/cron.d/jeromelu`, source-discovery docs/tests
- **What.** Add scheduled deterministic source-discovery execution with dry-run/operator controls.
- **How to verify.** Script syntax, dry-run command proof, cron shape check.
- **Proof notes.** Waiting for SCOUT-DETERMINISTIC-YT review/integration.

### SCOUT-SOURCE-HEALTH

- **Plan.** [Scout roadmap completion](./PLAN.md#2026-05-30---scout-roadmap-completion)
- **State.** ready
- **Owner.** unassigned
- **Branch.** `codex/scout-roadmap-source-health`
- **Depends-on.** SCOUT-YT-AGENT-RUNS
- **Touches.** source-health API/Scout modules, tests, source-health docs
- **What.** Detect stalled channels, unreachable sources, transcript fetch failures, and caption-regeneration risk using Scout run/source metadata.
- **How to verify.** Unit tests for stale/failed source classification and API/import checks.
- **Proof notes.** Waiting for SCOUT-YT-AGENT-RUNS review/integration.

---

## Completed work

Completed work is not kept here. When a work order passes review/test and is integrated, what it delivered is recorded in the active run report under [`docs/build/runs/`](./runs/) and the work order is removed from this file.
