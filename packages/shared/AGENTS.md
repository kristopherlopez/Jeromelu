# Shared Package Instructions

Read this before editing `packages/shared/**`.

## Scope

`packages/shared` holds reusable contracts and helpers used by services, scripts, and tests. Changes here have broad blast radius.

## Required Context

- Code principles: root `AGENTS.md`
- Invariants: `docs/build/META.md`
- Tests: `tests/unit/shared/`
- Pyright scope: `pyproject.toml`

## Rules

- Keep dependencies lean. Shared code should not pull in service-specific or heavyweight ML packages.
- Put shared types, constants, and contracts here instead of importing from sibling implementations.
- Preserve stable function signatures unless the work order explicitly updates every caller.
- Add mirrored unit tests under `tests/unit/shared/`.
- Pyright currently focuses here; keep annotations and public contracts clear.
- Do not read `.env` or make network calls at import time.
