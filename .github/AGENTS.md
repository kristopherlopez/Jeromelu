# GitHub Workflow Instructions

Read this before editing `.github/**`.

## Scope

GitHub Actions owns tests, deploy, Terraform planning, and scheduled reports.

## Required Context

- CI/CD docs: `docs/ops/ci-cd.md`
- Workflow files: `.github/workflows/*.yml`
- Process and security invariants: `docs/build/META.md`

## Rules

- Keep `tests.yml` as the deploy gate for normal `master` pushes.
- Manual `workflow_dispatch` on deploy is the emergency override; do not weaken the normal gate casually.
- Update `docs/ops/ci-cd.md` when workflow behavior, path filters, gates, secrets, or schedules change.
- Do not add secrets to workflow files. Use GitHub Actions secrets and document required names.
- Self-hosted runner jobs run on the Lightsail box; be conservative with disk, memory, Docker pulls, and long-running commands.
- Terraform workflow is plan-only; apply remains manual.
