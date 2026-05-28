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

> All eight tasks implement **PLAN.md § 2026-05-28: Scout Phase 4 — nrl.com casualty ward + ladder + retire worker-scraper.** Scope is NRL only (competition 111), season 2026, forward-only — historical backfill is Phase 5. The pipelines, extractors, make targets, and migrations already exist; these tasks add the D8 drift contract, extractor tests, scheduling, the seed, and retire the orphaned worker. Casualty + ladder are single-envelope fetches → drift aborts with `HTTPException(500)` (the **draw** precedent), not the non-aborting match-centre pattern.

### TASK-28 — retire worker-scraper (delete dir + doc sweep)

- **What:** Per the plan's *Files deleted* + *Documentation updates* (D4). Delete the entire `services/worker-scraper/` directory. Update the live docs that reference it: `docs/agents/system/scraper.md` (mark the Temporal worker **retired/deleted**), `docs/agents/crew/scout/charter.md` (D4 → done), `docs/agents/crew/scout/roadmap.md` (Phase 4 retirement line → done), `docs/agents/crew/scout/README.md`, `docs/agents/system/README.md`, `docs/architecture/08-technology-stack.md`, `docs/pages/wiki/data-feeds.md`. Leave `docs/archive/prd/jeromelu-ai-scraper-prd.md` (historical archive). Append the worker-scraper retirement to the Phase 4 run report.
- **How to verify:** `services/worker-scraper/` gone. `grep -rn "worker-scraper\|worker_scraper"` across the repo returns **only** `docs/archive/prd/` matches — zero code, compose (`docker/*.yml`), CI (`.github/`), deploy-script, or live-doc references. `make -n` unaffected; the api package still imports cleanly (nothing imported from the deleted dir — pre-verified at planning time). Confirmed orphaned at planning time: not present in either compose file, CI, or `Makefile`.
- **Proof notes:** _(empty at review time)_


## Completed work

Completed tasks are not kept here. When a task passes review and is checked off, what it delivered is recorded in the active run report under [`docs/build/runs/`](./runs/) and the task is removed from this file. This queue holds only open/in-flight work.
