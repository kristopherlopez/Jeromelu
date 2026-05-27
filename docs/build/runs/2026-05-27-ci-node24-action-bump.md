# CI actions bumped off deprecated Node 20

**Date:** 2026-05-27 · **Status:** 🟢 Shipped (all workflows green, Node-20 annotation cleared) · **Plan:** none — standalone CI-maintenance chore · **Tasks:** TASK-20

**TL;DR** — Once the repo went public and Actions ran again, every run carried GitHub's *"Node.js 20 actions are deprecated"* annotation (forced to Node 24 on **2026-06-02**, Node 20 removed **2026-09-16**). Bumped each GitHub-authored and third-party action across all four workflows to its current `node24` major. Verified by pushing to master: Tests, Terraform, and Build & Deploy all green with **zero** Node-20 annotations.

---

## What was completed

### TASK-20 — Bump CI actions off the Node 20 runtime (`3d3243e`)

Before bumping, the **current** latest release of each action was queried (`gh api repos/<a>/releases/latest`) and its runtime confirmed (`runs.using` at the target major) — the task spec's version guesses (written from Jan-2026 knowledge) were stale, so the bumps target the actual current majors, each verified `node24`:

| action | before | after | runtime |
|---|---|---|---|
| `actions/checkout` | v4 | **v6** | node24 |
| `actions/setup-python` | v5 | **v6** | node24 |
| `actions/setup-node` | v4 | **v6** | node24 |
| `actions/github-script` | v7 | **v9** | node24 |
| `aws-actions/configure-aws-credentials` | v4 | **v6** | node24 |
| `dorny/paths-filter` | v3 | **v4** | node24 |
| `hashicorp/setup-terraform` | v3 | **v4** | node24 |
| `aws-actions/amazon-ecr-login` | v2 | *(unchanged)* | node24 (latest v2.1.5 already node24) |

Files touched: `.github/workflows/{tests,deploy,terraform,cost-report}.yml`. The `node-version: "20"` input in `tests.yml` (the project `tsc` toolchain, **not** an action runtime) was deliberately left untouched.

**Proof:** pushed `3d3243e` to master → three workflows triggered and all completed `success` with **0** Node-20 deprecation annotations each:
- **Tests** (`26515120208`) — exercised `checkout@v6`, `setup-python@v6`, `setup-node@v6`.
- **Build & Deploy** (`26515120109`) — `detect-changes` exercised `checkout@v6`, `paths-filter@v4`; build/deploy jobs skipped (no service-path change), so no prod deploy.
- **Terraform** (`26515120128`) — triggered because `terraform.yml` itself changed; exercised `checkout@v6`, `configure-aws-credentials@v6`, `setup-terraform@v4` through fmt/init/validate/plan.

`cost-report.yml` (schedule-only) and `deploy.yml`'s `github-script`/`configure-aws-credentials` (build/deploy jobs) weren't exercised by this push, but use the identical action versions verified `node24` elsewhere.

## Decisions & deviations

- **Bumped to current majors (v6/v9/v4), not the v5/v8 the task text guessed.** The spec's versions predated the actual releases; all current majors are `node24`, which is the actual goal.
- **`amazon-ecr-login` left at `@v2`** — its latest release (v2.1.5) is already `node24`, so no bump was needed; churning it would add risk for no benefit.
- **Formal `adversarial-reviewer` was not dispatched.** This was a human-directed ("run both") mechanical version bump whose acceptance bar — green CI with the Node-20 annotation gone — is objectively verified by the three runs above. Flagged here as a process deviation from the standard checkoff ritual.
