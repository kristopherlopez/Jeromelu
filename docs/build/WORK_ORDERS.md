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
- **State.** done-pending-report
- **Owner.** integrated by coordinator
- **Branch.** `codex/scout-roadmap-ops-sched` / `C:\tmp\Jeromelu-ops-sched`
- **Depends-on.** none
- **Touches.** `scripts/scout-refresh.sh`, `scripts/scout-populate.sh`, `scripts/cron.d/jeromelu`, `scripts/data/populate/README.md`, related Scout/ops docs
- **What.** Add missing operator scheduling/wrapper coverage for shipped deterministic Scout pipelines and document the prod/runtime expectations.
- **How to verify.** Shell syntax checks, wrapper dry-runs, cron shape checks, docs review.
- **Proof notes.** Integrated via branch `codex/scout-roadmap-ops-sched` at `2e4904ba2c7ceb04cdfba437d0018cdf7a3837ae`. Reviewer PASS WITH CONCERNS; coordinator addressed cron-digest visibility and docs scoping before merge.

### SCOUT-YT-AGENT-RUNS

- **Plan.** [Scout roadmap completion](./PLAN.md#2026-05-30---scout-roadmap-completion)
- **State.** done-pending-report
- **Owner.** integrated by coordinator
- **Branch.** `codex/scout-roadmap-yt-agent-runs` / `C:\tmp\Jeromelu-scout-yt-agent-runs`
- **Depends-on.** none
- **Touches.** `services/api/app/scout/youtube/refresh.py`, `services/api/app/routers/recon.py`, `tests/unit/api/scout/test_youtube_refresh_audit.py`, data-lineage docs
- **What.** Standardise deterministic YouTube/recon jobs onto `agent_runs` so downstream health/dashboard work has a durable run source.
- **How to verify.** Unit tests for audit rows, import checks, docs review.
- **Proof notes.** Integrated via branch `codex/scout-roadmap-yt-agent-runs` at `12ec6268bbda013c74dc18ea1ae8830ca8503078`. Initial reviewer BLOCK fixed; re-review PASS WITH CONCERNS. Remaining concern: cron-level monitoring sees HTTP 200 partial failures, while `agent_runs` marks them failed.

### SCOUT-RECON-UI

- **Plan.** [Scout roadmap completion](./PLAN.md#2026-05-30---scout-roadmap-completion)
- **State.** done-pending-report
- **Owner.** integrated by coordinator
- **Branch.** `codex/scout-roadmap-recon-ui` / `C:\tmp\Jeromelu-recon-ui`
- **Depends-on.** none
- **Touches.** `services/web/src/app/admin/AdminClient.tsx`, `services/web/src/app/admin/ReconCandidatesPanel.tsx`
- **What.** Add the admin recon candidate review queue UI.
- **How to verify.** Web lint/typecheck and reviewer inspection for admin UI regressions.
- **Proof notes.** Integrated via branch `codex/scout-roadmap-recon-ui` at `dcaf99cee88367bb91899bebd1190fcb4497ea13`. Reviewer concerns about nullable arrays, min-score validation, and pending labels were patched before merge.

### SCOUT-MEDIA-DRAIN

- **Plan.** [Scout roadmap completion](./PLAN.md#2026-05-30---scout-roadmap-completion)
- **State.** done-pending-report
- **Owner.** integrated by coordinator
- **Branch.** `codex/scout-roadmap-media-drain-v2` / `C:\tmp\Jeromelu-media-drain`
- **Depends-on.** none
- **Touches.** `services/api/app/scout/media/drain.py`, `services/api/app/scout/media/cli/drain_audio.py`, `services/api/app/analyst/transcribe_drain_cli.py`, drain tests, `Makefile`, ingestion/transcription docs
- **What.** Add a reusable recurring drain surface for pending media ingestion/transcription work.
- **How to verify.** CLI help checks, drain unit tests, docs review.
- **Proof notes.** Integrated via branch `codex/scout-roadmap-media-drain-v2` at `663c02200e4adafa610cd234c3e49ae4d9bb38ae`. Initial reviewer BLOCK fixed; re-review PASS.

### SCOUT-DETERMINISTIC-YT

- **Plan.** [Scout roadmap completion](./PLAN.md#2026-05-30---scout-roadmap-completion)
- **State.** done-pending-report
- **Owner.** integrated by coordinator
- **Branch.** `codex/scout-roadmap-deterministic-yt` / `C:\tmp\Jeromelu-deterministic-yt`
- **Depends-on.** none
- **Touches.** `services/api/app/scout/source_discovery/**`, `services/api/app/scout/routes.py`, Scout/source-discovery docs, deterministic-discovery tests
- **What.** Land the deterministic YouTube discovery surface from the Scout architecture plan.
- **How to verify.** Unit tests for filtering/scoring/persistence, CLI help, route import checks.
- **Proof notes.** Integrated via branch `codex/scout-roadmap-deterministic-yt` at `9d89b0d4078f2af0c8a184248d4ac291c7608a04`. Reviewer concerns about dry-run output and route/CLI coverage were patched before merge.

### SCOUT-DASHBOARD-API

- **Plan.** [Scout roadmap completion](./PLAN.md#2026-05-30---scout-roadmap-completion)
- **State.** in-flight
- **Owner.** worker `019e76c0-73c0-7290-b49b-c18ac53d25de`
- **Branch.** `codex/scout-roadmap-dashboard-api` / `C:\tmp\Jeromelu-dashboard-api`
- **Depends-on.** SCOUT-YT-AGENT-RUNS
- **Touches.** `services/api/app/routers/**`, Scout dashboard API tests, dashboard docs
- **What.** Expose a Scout pipeline health endpoint backed by `agent_runs`, grouped by `detail_json.pipeline`.
- **How to verify.** Unit tests for grouping/status/row-count response shape and import/API checks.
- **Proof notes.** Worker Volta running.

### SCOUT-DASHBOARD-WEB

- **Plan.** [Scout roadmap completion](./PLAN.md#2026-05-30---scout-roadmap-completion)
- **State.** ready
- **Owner.** unassigned
- **Branch.** `codex/scout-roadmap-dashboard-web`
- **Depends-on.** SCOUT-DASHBOARD-API, SCOUT-RECON-UI
- **Touches.** `services/web/src/app/admin/**`
- **What.** Add the operator Scout dashboard UI after the API response shape is stable.
- **How to verify.** Web typecheck/lint and browser/UI smoke check.
- **Proof notes.** Sequential behind dashboard API; recon UI is integrated.

### SCOUT-SOURCE-DISCOVERY-SCHED

- **Plan.** [Scout roadmap completion](./PLAN.md#2026-05-30---scout-roadmap-completion)
- **State.** in-flight
- **Owner.** worker `019e76c0-b8eb-7ae2-ad78-f7fe36abe089`
- **Branch.** `codex/scout-roadmap-source-discovery-sched` / `C:\tmp\Jeromelu-source-discovery-sched`
- **Depends-on.** SCOUT-DETERMINISTIC-YT
- **Touches.** `scripts/scout-refresh.sh`, `scripts/cron.d/jeromelu`, source-discovery docs/tests
- **What.** Add scheduled deterministic source-discovery execution with dry-run/operator controls.
- **How to verify.** Script syntax, dry-run command proof, cron shape check.
- **Proof notes.** Worker Pascal running.

### SCOUT-SOURCE-HEALTH

- **Plan.** [Scout roadmap completion](./PLAN.md#2026-05-30---scout-roadmap-completion)
- **State.** in-flight
- **Owner.** worker `019e76c1-06af-7531-a3c0-73fc4a63fc2f`
- **Branch.** `codex/scout-roadmap-source-health` / `C:\tmp\Jeromelu-source-health`
- **Depends-on.** SCOUT-YT-AGENT-RUNS
- **Touches.** source-health API/Scout modules, tests, source-health docs
- **What.** Detect stalled channels, unreachable sources, transcript fetch failures, and caption-regeneration risk using Scout run/source metadata.
- **How to verify.** Unit tests for stale/failed source classification and API/import checks.
- **Proof notes.** Worker Nash running.

---

## Completed work

Completed work is not kept here. When a work order passes review/test and is integrated, what it delivered is recorded in the active run report under [`docs/build/runs/`](./runs/) and the work order is removed from this file.
