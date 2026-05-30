---
tags: [area/build, area/scout]
---

# Scout roadmap completion

**Date:** 2026-05-30
**Status:** Shipped
**Plan:** completed and removed from [`docs/build/PLAN.md`](../PLAN.md)

## Coordinator notes

This run closes the implementable Scout roadmap gaps using parallel worktree threads with explicit dependency boundaries.

The parent checkout at `C:\Users\krist\ClaudeProjects\Jeromelu` is intentionally not used for integration because it contains unrelated/accidental dirty state. Coordinator integration is happening in the clean worktree `C:\tmp\Jeromelu-integrate` on branch `codex/scout-roadmap-integrate`.

## First-wave branches

| Work order | Branch | Commit | Review |
|---|---|---|---|
| SCOUT-OPS-SCHEDULES | `codex/scout-roadmap-ops-sched` | `2e4904ba2c7ceb04cdfba437d0018cdf7a3837ae` | PASS WITH CONCERNS; addressed |
| SCOUT-YT-AGENT-RUNS | `codex/scout-roadmap-yt-agent-runs` | `12ec6268bbda013c74dc18ea1ae8830ca8503078` | PASS WITH CONCERNS after blocker fix |
| SCOUT-RECON-UI | `codex/scout-roadmap-recon-ui` | `dcaf99cee88367bb91899bebd1190fcb4497ea13` | PASS WITH CONCERNS; addressed |
| SCOUT-MEDIA-DRAIN | `codex/scout-roadmap-media-drain-v2` | `663c02200e4adafa610cd234c3e49ae4d9bb38ae` | PASS after blocker fix |
| SCOUT-DETERMINISTIC-YT | `codex/scout-roadmap-deterministic-yt` | `9d89b0d4078f2af0c8a184248d4ac291c7608a04` | PASS WITH CONCERNS; addressed |

All first-wave branches are now integrated into `codex/scout-roadmap-integrate`.

- SCOUT-OPS-SCHEDULES integrated at `2e4904ba2c7ceb04cdfba437d0018cdf7a3837ae`.
- SCOUT-YT-AGENT-RUNS integrated at `12ec6268bbda013c74dc18ea1ae8830ca8503078` after blocker fix and re-review.
- SCOUT-RECON-UI integrated at `dcaf99cee88367bb91899bebd1190fcb4497ea13` after reviewer concern fixes.
- SCOUT-MEDIA-DRAIN integrated at `663c02200e4adafa610cd234c3e49ae4d9bb38ae` after blocker fix and re-review.
- SCOUT-DETERMINISTIC-YT integrated at `9d89b0d4078f2af0c8a184248d4ac291c7608a04` after reviewer concern fixes.

## Second-wave branches

| Work order | Branch | Thread | Status |
|---|---|---|---|
| SCOUT-DASHBOARD-API | `codex/scout-roadmap-dashboard-api` | `019e76c0-73c0-7290-b49b-c18ac53d25de` | Integrated at `462cbeba20d1dd5804a1d3238355900c95b2323a` |
| SCOUT-SOURCE-DISCOVERY-SCHED | `codex/scout-roadmap-source-discovery-sched` | `019e76c0-b8eb-7ae2-ad78-f7fe36abe089` | Integrated at `aaec07e5bfe441755831c15ae91a9ffbf3c7b934` |
| SCOUT-SOURCE-HEALTH | `codex/scout-roadmap-source-health` | `019e76c1-06af-7531-a3c0-73fc4a63fc2f` | Integrated at `a9f25ad599d0e57e5867f287dbfd3e394c19cc12` |
| SCOUT-DASHBOARD-WEB | `codex/scout-roadmap-dashboard-web` | `019e76e4-48fc-7f23-a4de-e92dd2fb3b82` | Integrated at `8b2ca56b52d2f52362e08ae28c3c9fc08492c7a7` |

- SCOUT-DASHBOARD-API added `GET /api/admin/scout/dashboard`, a bounded Scout `agent_runs` rollup grouped by `detail_json.pipeline`, with route registration, docs, grouping/null-detail/query tests, and a cap for broad detail objects.
- SCOUT-SOURCE-DISCOVERY-SCHED added `source-discovery-youtube` support to `scripts/scout-refresh.sh`, a weekly cron entry, and operator docs. The coordinator patched lazy season resolution so source-discovery dry-run does not call `date`.
- SCOUT-SOURCE-HEALTH added route-free source health classification over Scout run/channel/source metadata, shared Scout pipeline constants, DB loaders, and unit coverage for stale runs, failed runs, stale channel metrics, invalid collected rows, pending audio, transcription failures, and caption-regeneration risk.
- SCOUT-DASHBOARD-WEB added the Scout Dashboard admin tab and `ScoutDashboardPanel`, with loading/error/empty/refresh states, row-window controls, pipeline status rollups, recent failure/cost counters, compact detail fields, and roadmap docs updated to mark Phase 6 shipped.

## Verification

- Integrated API import check passed for Scout routes, dashboard, source discovery, source health, media drain, and transcription drain modules using the pgAdmin Python runtime with explicit repo/venv `sys.path`.
- `tests/unit/api/scout/test_dashboard.py`, `tests/unit/api/scout/test_source_health.py`, and `tests/unit/api/scout/test_youtube_refresh_audit.py`: 19 passed in final integration.
- `scripts/scout-refresh.sh` syntax check passed via Git Bash.
- `scripts/scout-refresh.sh source-discovery-youtube --dry-run` emitted `https://api.jeromelu.ai/api/admin/scout/source-discovery/youtube?max_results=10&max_videos=25&min_score=0.55`.
- Final web typecheck passed with `node node_modules/typescript/bin/tsc --noEmit --incremental false`.
- Targeted admin ESLint passed with one pre-existing `react-hooks/set-state-in-effect` warning in `AdminClient.tsx` transcript diff code.
- Local Next dev server smoke passed with webpack mode: `GET http://127.0.0.1:3002/admin` returned 200 and rendered the admin shell.
- `git diff --check` passed.

## Verification caveats

The Windows API virtualenv currently points at a missing Python base executable. The coordinator used `C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe` with explicit repo/venv `sys.path` insertion for API import and pytest checks.

The global `npm`/`npx` shim is broken in this environment, so web checks used local `node_modules` entrypoints. A temporary junction to the parent `services/web/node_modules` was needed in the integration worktree. Turbopack rejected that junction during dev-server startup, so the local smoke used `next dev --webpack`.

The in-app browser connector failed to start in this Windows sandbox (`windows sandbox failed: spawn setup refresh`). No Playwright/Puppeteer package is installed locally. Browser visual smoke is therefore deferred, but the local Next server did render `/admin` successfully over HTTP.

## Outstanding

- Cron-level monitoring still sees HTTP 200 partial failures even though `agent_runs.status='failed'` now records partial failure state. That was a non-blocking reviewer concern for SCOUT-YT-AGENT-RUNS and should be tracked as a future observability improvement if operator alerting depends on HTTP status.
