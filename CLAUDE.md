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
