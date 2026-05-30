# Test Instructions

Read this before editing `tests/**`.

## Scope

Tests are split by runtime requirements: unit, integration, and evals.

## Required Context

- Test layout: `tests/README.md`
- CI: `.github/workflows/tests.yml`
- CI/CD docs: `docs/ops/ci-cd.md`

## Rules

- Mirror the source tree when adding tests.
- Unit tests must be fast, deterministic, and free of DB, S3, live HTTP, env vars, and heavyweight ML imports.
- Integration tests hold DB/S3/live endpoint checks and should be env-flagged where appropriate.
- Evals are LLM-graded, non-deterministic, and may cost money. Do not run them casually.
- Prefer pure helper tests over broad mocks.
- Scout fixture tests should use checked-in canonical payloads under `tests/fixtures/scout/`.
- Do not import modules that drag `torch`, `pyannote`, or other heavy deps into unit collection.
