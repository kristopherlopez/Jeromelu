# Scout Instructions

Read this before editing `services/api/app/scout/**`.

## Scope

Scout is the API-side acquisition boundary. It captures upstream data and archives raw responses. Downstream interpretation belongs outside Scout unless a work order explicitly says otherwise.

## Required Context

- Package layout: `services/api/app/scout/README.md`
- Pipeline README: `services/api/app/scout/<pipeline>/README.md`
- Data invariants: `docs/build/META.md`
- Tests and fixtures: `tests/unit/api/scout/`, `tests/integration/scout/`, `tests/fixtures/scout/`
- Data docs when DB projections change: `docs/operations/data-catalogue/`, `docs/operations/data-lineage/`, `docs/operations/data-sources/`

## Rules

- Capture raw upstream payloads before DB projection.
- For deterministic pipelines, keep the local pattern: `fetcher.py`, `models.py`, `routes.py`, `README.md`.
- Use strict Pydantic models for D8/drift-guarded payloads. Keep `extra="forbid"` where the local pipeline pattern uses it.
- Every scraper module needs a fixture-backed drift test. Do not silently auto-adapt to upstream schema drift.
- Keep archive paths, cadence, source URLs, and drift notes current in the pipeline README.
- If the payload feeds DB tables, update catalogue, lineage, and source docs in the same changeset.
- Tests should mirror the pipeline name across unit, integration, and fixtures.
