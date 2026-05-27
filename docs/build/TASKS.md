# Jaromelu Task Queue

Persistent queue for the long-lived implementer session. The implementer reads top-down, completes one task at a time, dispatches `adversarial-reviewer` against the diff + task + plan, and only checks off after the review passes.

## Format

Each task is a level-3 heading with three labelled blocks:

- **What** — exactly what to do. References a section of `PLAN.md`.
- **How to verify** — concrete checks. Commands, files, expected output. Bar: "if satisfied exactly as written, the result is trustworthy."
- **Proof notes** — an optional in-flight scratchpad only. The **authoritative** proof record is the task's entry in the active run report under [`docs/build/runs/`](./runs/), written **at checkoff (after the review passes)**.

**Proof timing (important for reviewers):** under the run-report ritual, proof is recorded into the run report *at checkoff*, which is downstream of the review. So an **empty Proof-notes block at review time is expected and is NOT a blocker** — the reviewer verifies the diff against the spec and runs the **How to verify** checks itself; proof recording is a post-pass step.

Mark as `[x]` only after `adversarial-reviewer` passes. Once it passes, record what the task delivered in the active run report under [`docs/build/runs/`](./runs/) and **remove it from this file** — TASKS.md holds only the live queue, not a completed-task graveyard (see the run-report ritual in [META.md](./META.md)).

### Tags

Prefix the title with optional tags in square brackets:

- `[P0]`, `[P1]`, `[P2]`, `[P3]` — severity (from `issue-triager`)
- `[BLOCKED: reason]` — implementer hit a wall; needs human input

---

## Open tasks

### [BLOCKED: awaiting human VACUUM FULL on prod] TASK-09: Prod reclaim runbook + deferred VACUUM FULL size verification

Implements PLAN.md § 2026-05-27 "Change-only storage" — the reclaim half. Authors the one-time prod maintenance runbook and closes out the initiative once the space is returned. The actual `VACUUM (FULL)` is a **human-run prod step** (brief table lock) — this task delivers the runbook + records the size drop when observed.

> **Doc deliverable DONE 2026-05-27** (commit `a8c9ebf`, adversarial-reviewer PASS WITH CONCERNS — both non-blocking doc-traceability nits). `docs/operations/metrics-dedup-runbook.md` written + linked from the video_metrics catalogue page. **Only the deferred verification remains:** a human runs `VACUUM (FULL, ANALYZE) video_metrics; VACUUM (FULL, ANALYZE) channel_metrics;` on prod (per the runbook) **after migration 070 has been applied on prod**, then pastes the before/after `pg_total_relation_size` output (≈641 MB → ≈191 MB) into the run report. Then mark `[x]`, finalise the run report to Shipped, and remove the plan from PLAN.md's Active section. Do NOT run the prod VACUUM without explicit human go-ahead.

**What**

1. Create `docs/operations/metrics-dedup-runbook.md`: purpose (one-time reclaim after migration 070), preconditions (070 applied on prod; run off-hours; 40 GB free disk confirms headroom), the exact commands:
   ```sql
   VACUUM (FULL, ANALYZE) video_metrics;
   VACUUM (FULL, ANALYZE) channel_metrics;
   ```
   the `ACCESS EXCLUSIVE` lock warning (table unavailable for the rewrite duration — seconds to low minutes for the ~191 MB result), the before/after size query:
   ```sql
   SELECT pg_size_pretty(pg_total_relation_size('video_metrics')) AS video,
          pg_size_pretty(pg_total_relation_size('channel_metrics')) AS channel;
   ```
   expected `video_metrics` 641 MB → ~191 MB, and a "no rollback needed — `VACUUM` is non-destructive" note. Link it from `docs/operations/data-catalogue/video_metrics.md`.
2. Add a row/pointer to whatever ops-doc index covers `docs/operations/` runbooks if one exists (check `docs/operations/` for an index; if none, the catalogue link suffices).

**How to verify**

- `docs/operations/metrics-dedup-runbook.md` exists with the commands, lock warning, before/after query, and expected sizes exactly as above. The catalogue page links to it.
- `git diff --cached --stat` shows only the runbook + the catalogue link edit.
- **Deferred (gates checkoff):** after the human runs the `VACUUM (FULL, ANALYZE)` on prod, capture the before/after `pg_total_relation_size` output showing `video_metrics` dropped to ~191 MB (±). Tag `[BLOCKED: awaiting human VACUUM FULL on prod]` until then — mirror the TASK-06 deferred-verification pattern; do not run `VACUUM FULL` on prod without explicit human go-ahead.

**Proof notes**
_(implementer fills in: runbook path, deferred before/after prod size output once the human runs the VACUUM)_


### [P2] TASK-20: Bump CI actions off deprecated Node 20 runtime

Standalone CI-maintenance chore (no PLAN.md initiative). Surfaced 2026-05-27 from a live GitHub Actions annotation once the repo went public and runs started executing again:

> *"Node.js 20 actions are deprecated … Actions will be forced to run with Node.js 24 by default starting June 2nd, 2026. Node.js 20 will be removed from the runner on September 16th, 2026."*

Hard deadlines: **forced to Node 24 on 2026-06-02**, **Node 20 removed 2026-09-16**. Bump the GitHub-authored actions to their Node 24 releases before June 2 to avoid surprise breakage; sweep third-party actions in the same pass.

**What**

1. Across all four workflows in `.github/workflows/`, bump the **action ref versions** (not job logic) to the latest Node-24 releases:
   - `actions/checkout@v4` → `@v5` — in `tests.yml`, `deploy.yml`, `terraform.yml`, `cost-report.yml`
   - `actions/setup-python@v5` → `@v6` — in `tests.yml`, `cost-report.yml`
   - `actions/setup-node@v4` → `@v5` — in `tests.yml`
   - `actions/github-script@v7` → latest (confirm it ships a Node-24 release; bump if so) — in `deploy.yml`, `terraform.yml`
2. Third-party actions (`aws-actions/configure-aws-credentials`, `aws-actions/amazon-ecr-login`, `dorny/paths-filter`, `hashicorp/setup-terraform`) — check each for a published Node-24-compatible release and bump if available. If a given action has no Node-24 release yet, leave it pinned and note that in the run report (don't force-bump to a non-existent tag).
3. **Do NOT touch the `node-version: "20"` input in `tests.yml`** (line ~65). That sets the Node the project's `tsc` typecheck runs under — it is unrelated to the action-runtime deprecation and changing it is a separate decision. The deprecation is about the JS runtime that executes the action itself, not the project toolchain version.

**How to verify**

- `git diff --cached .github/workflows/` shows only `uses:` ref version bumps (and nothing in the `node-version` input).
- Push to `master` (or open a PR): the `Tests` and `Build & Deploy` runs go green, and the **Node 20 deprecation annotation no longer appears** on the run (`gh run view <id>` → ANNOTATIONS section is clean of the Node.js-20 warning).
- For any third-party action deliberately left un-bumped (no Node-24 release yet), the run report names it and why.

**Proof notes**
_(implementer fills in: per-action before→after versions, link to the green run with no Node-20 annotation, any action left pinned + reason)_


## Completed work

Completed tasks are not kept here. When a task passes review and is checked off, what it delivered is recorded in the active run report under [`docs/build/runs/`](./runs/) and the task is removed from this file. This queue holds only open/in-flight work.
