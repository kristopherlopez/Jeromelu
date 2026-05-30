---
tags: [area/build, area/miner]
---

# Miner roadmap completion

**Date:** 2026-05-30
**Status:** Shipped
**Plan:** completed and removed from [`docs/build/PLAN.md`](../PLAN.md)

## Coordinator notes

This run closes the implementable Miner roadmap gaps using parallel worktree threads with explicit dependency boundaries.

The parent checkout at `C:\Users\krist\ClaudeProjects\Jeromelu` is intentionally not used for integration because it contains unrelated/accidental dirty state. Coordinator integration is happening in the clean worktree `C:\tmp\Jeromelu-integrate` on branch `codex/miner-roadmap-integrate`.

## First-wave branches

| Work order | Branch | Commit | Review |
|---|---|---|---|
| MINER-OPS-SCHEDULES | `codex/miner-roadmap-ops-sched` | `2e4904ba2c7ceb04cdfba437d0018cdf7a3837ae` | PASS WITH CONCERNS; addressed |
| MINER-YT-AGENT-RUNS | `codex/miner-roadmap-yt-agent-runs` | `12ec6268bbda013c74dc18ea1ae8830ca8503078` | PASS WITH CONCERNS after blocker fix |
| MINER-RECON-UI | `codex/miner-roadmap-recon-ui` | `dcaf99cee88367bb91899bebd1190fcb4497ea13` | PASS WITH CONCERNS; addressed |
| MINER-MEDIA-DRAIN | `codex/miner-roadmap-media-drain-v2` | `663c02200e4adafa610cd234c3e49ae4d9bb38ae` | PASS after blocker fix |
| MINER-DETERMINISTIC-YT | `codex/miner-roadmap-deterministic-yt` | `9d89b0d4078f2af0c8a184248d4ac291c7608a04` | PASS WITH CONCERNS; addressed |

All first-wave branches are now integrated into `codex/miner-roadmap-integrate`.

- MINER-OPS-SCHEDULES integrated at `2e4904ba2c7ceb04cdfba437d0018cdf7a3837ae`.
- MINER-YT-AGENT-RUNS integrated at `12ec6268bbda013c74dc18ea1ae8830ca8503078` after blocker fix and re-review.
- MINER-RECON-UI integrated at `dcaf99cee88367bb91899bebd1190fcb4497ea13` after reviewer concern fixes.
- MINER-MEDIA-DRAIN integrated at `663c02200e4adafa610cd234c3e49ae4d9bb38ae` after blocker fix and re-review.
- MINER-DETERMINISTIC-YT integrated at `9d89b0d4078f2af0c8a184248d4ac291c7608a04` after reviewer concern fixes.

## Second-wave branches

| Work order | Branch | Thread | Status |
|---|---|---|---|
| MINER-DASHBOARD-API | `codex/miner-roadmap-dashboard-api` | `019e76c0-73c0-7290-b49b-c18ac53d25de` | Integrated at `462cbeba20d1dd5804a1d3238355900c95b2323a` |
| MINER-SOURCE-DISCOVERY-SCHED | `codex/miner-roadmap-source-discovery-sched` | `019e76c0-b8eb-7ae2-ad78-f7fe36abe089` | Integrated at `aaec07e5bfe441755831c15ae91a9ffbf3c7b934` |
| MINER-SOURCE-HEALTH | `codex/miner-roadmap-source-health` | `019e76c1-06af-7531-a3c0-73fc4a63fc2f` | Integrated at `a9f25ad599d0e57e5867f287dbfd3e394c19cc12` |
| MINER-DASHBOARD-WEB | `codex/miner-roadmap-dashboard-web` | `019e76e4-48fc-7f23-a4de-e92dd2fb3b82` | Integrated at `8b2ca56b52d2f52362e08ae28c3c9fc08492c7a7` |

- MINER-DASHBOARD-API added `GET /api/admin/miner/dashboard`, a bounded Miner `agent_runs` rollup grouped by `detail_json.pipeline`, with route registration, docs, grouping/null-detail/query tests, and a cap for broad detail objects.
- MINER-SOURCE-DISCOVERY-SCHED added `source-discovery-youtube` support to `scripts/miner-refresh.sh`, a weekly cron entry, and operator docs. The coordinator patched lazy season resolution so source-discovery dry-run does not call `date`.
- MINER-SOURCE-HEALTH added route-free source health classification over Miner run/channel/source metadata, shared Miner pipeline constants, DB loaders, and unit coverage for stale runs, failed runs, stale channel metrics, invalid collected rows, pending audio, transcription failures, and caption-regeneration risk.
- MINER-DASHBOARD-WEB added the Miner Dashboard admin tab and `MinerDashboardPanel`, with loading/error/empty/refresh states, row-window controls, pipeline status rollups, recent failure/cost counters, compact detail fields, and roadmap docs updated to mark Phase 6 shipped.

## Verification

- Integrated API import check passed for Miner routes, dashboard, source discovery, source health, media drain, and transcription drain modules using the pgAdmin Python runtime with explicit repo/venv `sys.path`.
- `tests/unit/api/miner/test_dashboard.py`, `tests/unit/api/miner/test_source_health.py`, and `tests/unit/api/miner/test_youtube_refresh_audit.py`: 19 passed in final integration.
- `scripts/miner-refresh.sh` syntax check passed via Git Bash.
- `scripts/miner-refresh.sh source-discovery-youtube --dry-run` emitted `https://api.jeromelu.ai/api/admin/miner/source-discovery/youtube?max_results=10&max_videos=25&min_score=0.55`.
- Final web typecheck passed with `node node_modules/typescript/bin/tsc --noEmit --incremental false`.
- Targeted admin ESLint passed with one pre-existing `react-hooks/set-state-in-effect` warning in `AdminClient.tsx` transcript diff code.
- Local Next dev server smoke passed with webpack mode: `GET http://127.0.0.1:3002/admin` returned 200 and rendered the admin shell.
- `git diff --check` passed.

## Verification caveats

The Windows API virtualenv currently points at a missing Python base executable. The coordinator used `C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe` with explicit repo/venv `sys.path` insertion for API import and pytest checks.

The global `npm`/`npx` shim is broken in this environment, so web checks used local `node_modules` entrypoints. A temporary junction to the parent `services/web/node_modules` was needed in the integration worktree. Turbopack rejected that junction during dev-server startup, so the local smoke used `next dev --webpack`.

The in-app browser connector failed to start in this Windows sandbox (`windows sandbox failed: spawn setup refresh`). No Playwright/Puppeteer package is installed locally. Browser visual smoke is therefore deferred, but the local Next server did render `/admin` successfully over HTTP.

## Outstanding

- Cron-level monitoring still sees HTTP 200 partial failures even though `agent_runs.status='failed'` now records partial failure state. That was a non-blocking reviewer concern for MINER-YT-AGENT-RUNS and should be tracked as a future observability improvement if operator alerting depends on HTTP status.
