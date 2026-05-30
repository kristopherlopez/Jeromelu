# Jaromelu Thread Register

Live coordination state for Codex background threads working on the current goal. The coordinator owns this file.

## Rules

- Add a row when a worker, reviewer, tester, or triage thread is spawned for build work.
- Record the assigned work order, role, branch/worktree, `Touches`, and current status.
- Keep status current at phase transitions: `spawned`, `working`, `waiting-review`, `blocked`, `ready-to-integrate`, `integrated`, `archived`.
- Clear or archive rows after the run report records the completed work.
- Do not use this file as history. Durable history belongs in `docs/build/runs/`.

## Live Threads

| Thread ID | Role | Work order | Branch/worktree | Touches | Status | Notes |
|---|---|---|---|---|---|---|
| 019e76c0-73c0-7290-b49b-c18ac53d25de | implementer | SCOUT-DASHBOARD-API | `codex/scout-roadmap-dashboard-api` / `C:\tmp\Jeromelu-dashboard-api` | `services/api/app/scout/dashboard*`, tests/docs | working | Worker: Volta |
| 019e76c0-b8eb-7ae2-ad78-f7fe36abe089 | implementer | SCOUT-SOURCE-DISCOVERY-SCHED | `codex/scout-roadmap-source-discovery-sched` / `C:\tmp\Jeromelu-source-discovery-sched` | scripts/cron/source-discovery docs | working | Worker: Pascal |
| 019e76c1-06af-7531-a3c0-73fc4a63fc2f | implementer | SCOUT-SOURCE-HEALTH | `codex/scout-roadmap-source-health` / `C:\tmp\Jeromelu-source-health` | `services/api/app/scout/source_health.py`, tests/docs | working | Worker: Nash |
