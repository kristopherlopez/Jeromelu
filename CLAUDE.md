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
