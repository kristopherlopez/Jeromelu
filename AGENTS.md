## Build Operating Model

Jaromelu is built through explicit Codex goals coordinated across bounded threads. The human supplies the objective and constraints; the coordinator owns the Codex goal, decomposes it into dispatchable work orders, fans out independent slices to worker/reviewer/tester threads, and integrates proof back into `main`.

**Read at session start:**
- **Coordinator / planner sessions** — [docs/build/META.md](./docs/build/META.md) (process rules + invariants), [docs/build/PLAN.md](./docs/build/PLAN.md) (active goal plans), [docs/build/WORK_ORDERS.md](./docs/build/WORK_ORDERS.md) (dispatchable slices), and [docs/build/THREADS.md](./docs/build/THREADS.md) (live thread register).
- **Worker / reviewer / tester sessions** — read [docs/build/META.md](./docs/build/META.md), the assigned plan section, and the assigned work order only. Do not scan for unrelated queue work.
- **Other sessions** (triage, Q&A, ad-hoc) — skip the work-order system. Read [docs/build/META.md](./docs/build/META.md) only if you're about to touch code.

**Roles** (charters in [.codex/agents/](./.codex/agents/)): `coordinator`, `planner`, `implementer` (worker), `adversarial-reviewer`, `black-box-tester`, `issue-triager`, `deep-code-reviewer`.

**Threading rule:** the coordinator owns `main`, the run report, and final verification. Worker threads own one work order on a dedicated `codex/<goal>-<slice>` branch/worktree with declared `Touches`. Reviewer and tester threads are read-only unless explicitly assigned a follow-up fix. Two threads may run at once only when their `Touches` sets are disjoint and no dependency connects them.

---

## Git Workflow

Coordinator-integrated changes land on `main`; worker threads push scoped branches for coordinator integration. Don't batch unrelated work. Full commit / staging / push rules (session-scoped staging, no `--no-verify`, no force-push to main, worker branches only) live in [META.md → Git & commit discipline](./docs/build/META.md#git--commit-discipline).

---

## Code Principles

### Top-level imports

All imports at the top of the file, never inline inside functions or methods. Inline imports hide dependencies and surface errors at runtime instead of import time. The only exception is guarding an optional dependency that may not be installed — and even then, prefer failing fast at import.

### Interface consistency

When multiple implementations share a contract (e.g. generators for different LLM frameworks), they must follow the same structure: consistent class naming (`OpenAIGenerator`, `ClaudeGenerator`, `LangChainGenerator` — not `QAGenerator`, `ClaudeAgentGenerator`, `LangChainQAGenerator`), the same method signatures, the same metadata keys, and shared helpers via a common base class. Implementations should be interchangeable.

### Separation of concerns

Shared types, constants, and contracts live in their own module — never inside a specific implementation file. A false dependency between siblings (e.g. `generate_claude` importing from `generate_openai`) makes the code fragile.

---

## Documentation Discipline

Treat docs as production code. Full rules (which docs to update per change, planner "Documentation Updates" section requirement) live in [META.md → Documentation discipline](./docs/build/META.md#documentation-discipline). Background-execution carve-out for approved work orders lives there too.

---

## Testing

Three tiers under `tests/` — see `tests/README.md` for the full layout map:

- `tests/unit/` — fast, no IO, no env vars. Default tier; mirrors the source tree (`shared/`, `api/`, `gpu/`, `scripts/`). Run with `make test`.
- `tests/integration/` — DB / S3 / external infra required. Empty placeholder for now.
- `tests/evals/` — DeepEval LLM-graded suites. Costs $$ per run. Run with `make test-eval`.

When adding a test, mirror the source path under the matching tier. Pytest's `pythonpath` is preconfigured in `pytest.ini` for `services/api`, `packages/shared`, and the repo root, so imports like `from app.routers.admin import _stitch_segments` resolve without further setup. Dev-only deps live in the root `requirements-dev.txt`.
