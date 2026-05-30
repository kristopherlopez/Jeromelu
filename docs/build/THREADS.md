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
| _none_ | _none_ | _none_ | _none_ | _none_ | _none_ | Scout roadmap completion recorded in `docs/build/runs/2026-05-30-scout-roadmap-completion.md`. |
