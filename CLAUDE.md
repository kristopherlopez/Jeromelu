## Build Operating Model

The Jaromelu codebase is built by a small team of agents working a persistent task queue (Simon Last's "team-of-agents" model). The human's job is to keep vetted tasks flowing faster than they get drained; the implementer's job is to drain the queue with proof.

**Read at session start:**
- [docs/build/PLAN.md](./docs/build/PLAN.md) — active and archived plan docs
- [docs/build/TASKS.md](./docs/build/TASKS.md) — persistent queue (What / How to verify / Proof notes)
- [docs/build/META.md](./docs/build/META.md) — process rules and project invariants

**Roles** (charters in [.claude/agents/](./.claude/agents/)):
- `planner` — interviews, drafts plans, appends vetted tasks. Use BEFORE writing code.
- `implementer` — long-lived session, drains the queue.
- `adversarial-reviewer` — read-only per-task review before checkoff. Mandatory.
- `black-box-tester` — independent end-to-end verification.
- `issue-triager` — turns incoming pain into vetted tasks.
- `deep-code-reviewer` — periodic subsystem audit.

**Background-execution carve-out:** The user's global CLAUDE.md requires explicit approval before any background execution. Within the Jaromelu implementer session, background execution is **pre-approved by default for any task already in `docs/build/TASKS.md`** whose `What` block describes it. Ad-hoc background commands outside the queue still require human approval.

---

## Git Workflow

After every change (feature, fix, refactor, docs update), **commit and push to `main`** immediately. Do not batch changes or wait to be asked.

**Session-scoped commits:** Multiple Claude sessions may be working on different parts of the project concurrently. Only `git add` files that **this session** created or modified — never use `git add -A`, `git add .`, or stage files you didn't touch. If a file you need to commit has been modified by another session (unexpected diff), flag it to the user before staging. This prevents one session's commit from accidentally including another session's in-progress work.

---

## Code Principles

### Top-level imports

All imports must be at the top of the file, never inline inside functions or methods. Inline imports hide dependencies, make it unclear what a module requires, and make errors surface at runtime instead of import time. The only exception is guarding an optional dependency that may not be installed — and even then, prefer failing fast at import.

### Interface consistency

When multiple implementations share a contract (e.g. generators for different LLM frameworks), they must follow the same structure: consistent class naming (`OpenAIGenerator`, `ClaudeGenerator`, `LangChainGenerator` — not `QAGenerator`, `ClaudeAgentGenerator`, `LangChainQAGenerator`), the same method signatures, the same metadata keys, and shared helpers via a common base class. Implementations should be interchangeable — a caller shouldn't need to know which one it's talking to.

### Separation of concerns

Shared types, constants, and contracts must live in their own module — never inside a specific implementation file. If multiple implementations need the same interface (e.g. `QAResponse`, `Citation`, `SYSTEM_PROMPT`), extract it so each implementation depends on the shared contract, not on each other. A false dependency between siblings (e.g. `generate_claude` importing from `generate_openai`) makes the code fragile — changing one breaks the other for no good reason.

## Documentation Discipline (Mandatory - Never Skip)

You are extremely disciplined about keeping documentation in perfect sync with the code. For **every single task, feature, refactor, or plan** you create or suggest:

1. **Discovery Phase** (always do this first)
   - Explore and read all existing documentation:
     - README.md
     - docs/ folder (and any \*.md files)
     - Relevant inline docstrings / comments
     - This CLAUDE.md file itself
   - Identify what is relevant, outdated, or missing for the proposed changes.

2. **Planning Requirement**
   - Every plan you propose MUST contain a dedicated section called "**Documentation Updates**".
   - In that section explicitly list:
     - Which existing documents are impacted
     - What will be updated or newly created
     - Specific changes (e.g. "Add new endpoint X to API reference in docs/api.md", "Update architecture overview in README.md with new diagram description", "Create new migration guide for breaking change Y")

3. **Execution**
   - After code changes are complete, immediately update/create all affected documentation.
   - Documentation changes must be part of the same changeset when possible.
   - Never mark a task as "done" or propose final code until docs are current and consistent.

Stale or missing documentation is not acceptable. Treat docs as production code.

## Testing

Three tiers under `tests/` — see `tests/README.md` for the full layout map:

- `tests/unit/` — fast, no IO, no env vars. Default tier; mirrors the source tree (`shared/`, `api/`, `gpu/`, `scripts/`). Run with `make test`.
- `tests/integration/` — DB / S3 / external infra required. Empty placeholder for now.
- `tests/evals/` — DeepEval LLM-graded suites. Costs $$ per run. Run with `make test-eval`.

When adding a test, mirror the source path under the matching tier. Pytest's `pythonpath` is preconfigured in `pytest.ini` for `services/api` and `packages/shared`, so imports like `from app.routers.admin import _stitch_segments` and `from jeromelu_shared.scraping.nrl import normalize_team` resolve without further setup. Dev-only deps live in the root `requirements-dev.txt`.
