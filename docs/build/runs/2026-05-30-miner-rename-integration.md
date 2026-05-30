---
tags: [area/build, area/miner]
---

# Miner rename integration

**Date:** 2026-05-30
**Status:** Blocked at protected-branch review
**Branch:** `codex/miner-rename`
**PR:** <https://github.com/kristopherlopez/Jeromelu/pull/3>

## Summary

This run renames the Scout service surface to Miner and prepares the remaining
Phase 5 historical-backfill operations.

## Delivered

- Renamed `services/api/app/scout` to `services/api/app/miner` and updated API
  imports, routes, tests, scripts, docs, admin UI references, and shell helpers.
- Added migration `072_rename_scout_to_miner.sql` to rename Scout audit IDs,
  candidate tables, indexes, constraints, and check constraints to Miner.
- Expanded the Miner roadmap's multi-platform plan across MP0-MP6.
- Cleaned stale roadmap/README/architecture/source-discovery status language so
  shipped work and remaining backlog are not mixed.
- Fixed CI import sorting and Ruff formatting issues found by PR checks.

## Verification

- `pytest` passed before the branch was pushed.
- Targeted `ruff check` passed before the branch was pushed.
- `npm --prefix services/web exec tsc -- --noEmit --incremental false` passed
  before the branch was pushed.
- `git diff --check` passed.
- Git pre-push web typecheck passed.
- PR checks are green: pytest, web typecheck, web lint, Ruff check+format,
  Pyright, and Gitleaks.
- Phase 5 backfill CLI was smoke-checked against a dummy localhost API; it
  generated the expected Miner admin URL and failed only because no local API was
  listening.
- `scripts/miner-populate.sh nrlcom-current --no-op` printed the expected
  production projection plan under Git Bash.

## Blockers

- PR #3 is mergeable and green, but GitHub reports
  `reviewDecision=REVIEW_REQUIRED`. The authenticated GitHub account cannot
  approve its own PR, and auto-merge is disabled for the repository. I did not
  bypass branch protection with an integration/admin approval.
- Prod SSH access from this environment timed out:
  `ssh jeromelu-prod 'echo prod-ssh-ok'` could not connect to port 22. Because of
  that, I could not run the production migration command, read the prod
  `ADMIN_KEY`, deploy manually, or start the Phase 5 backfill on the box.

## Remaining Operator Steps

1. Approve and merge PR #3, or explicitly authorize an admin merge override.
2. Let the master `Tests` workflow and `Build & Deploy` workflow complete.
3. Run the prod migration from the Lightsail box using the documented META
   command for `packages/db/migrate.sh`.
4. Run Phase 5 archive backfills with `--archive-only --resume`:
   `nrlcom-draw` from 1908, `nrlcom-match-centre` from 2000, `nrlcom-ladder`,
   `nrlcom-stats`, and `supercoach-stats` from 2018.
5. Run `scripts/miner-populate.sh` historical projection phases after S3 archive
   backfill completes.
