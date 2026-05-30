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
| 019e76a3-9821-7d50-8c21-d1b768e3afe4 | adversarial-reviewer | SCOUT-OPS-SCHEDULES | `codex/scout-roadmap-ops-sched` / `C:\tmp\Jeromelu-ops-sched` | read-only | working | Reviewer: Ampere |
| 019e76a3-ca9f-76d3-875d-b1a7068a48db | adversarial-reviewer | SCOUT-YT-AGENT-RUNS | `codex/scout-roadmap-yt-agent-runs` / `C:\tmp\Jeromelu-scout-yt-agent-runs` | read-only | working | Reviewer: Sartre |
| 019e76a3-fc73-77c0-8133-7561ffd733d5 | adversarial-reviewer | SCOUT-RECON-UI | `codex/scout-roadmap-recon-ui` / `C:\tmp\Jeromelu-recon-ui` | read-only | working | Reviewer: Dirac |
| 019e76a4-2fa7-7990-9765-bb25971b3f16 | adversarial-reviewer | SCOUT-MEDIA-DRAIN | `codex/scout-roadmap-media-drain-v2` / `C:\tmp\Jeromelu-media-drain` | read-only | working | Reviewer: Mencius |
| 019e76a4-6590-7a60-89dc-63df55c90898 | adversarial-reviewer | SCOUT-DETERMINISTIC-YT | `codex/scout-roadmap-deterministic-yt` / `C:\tmp\Jeromelu-deterministic-yt` | read-only | working | Reviewer: Meitner |
