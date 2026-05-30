# Scripts Instructions

Read this before editing `scripts/**`.

## Scope

Scripts handle local operations, cron jobs, reports, deploy helpers, data utilities, and media/transcript tooling.

## Required Context

- CI/CD and cron docs: `docs/ops/ci-cd.md`
- Operational invariants: `docs/build/META.md`
- Cron source: `scripts/cron.d/jeromelu`
- Backfill-specific rules: `scripts/data/populate/AGENTS.md`

## Rules

- Treat scripts under cron or deploy paths as production code.
- Keep shell scripts portable for the documented runtime. Use explicit quoting for URLs and query strings.
- Do not hand-edit prod cron; edit `scripts/cron.d/jeromelu` and redeploy.
- Redact secrets from logs and report output.
- If a script changes runtime behavior, update the owning runbook or docs page.
- Data populate scripts have stricter idempotency and dry-run rules in `scripts/data/populate/AGENTS.md`.
