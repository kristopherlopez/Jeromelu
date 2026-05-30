# Database Package Instructions

Read this before editing `packages/db/**`.

## Scope

`packages/db` owns SQL migrations and migration execution. DB schema changes affect API models, scripts, data docs, and production operations.

## Required Context

- Migration invariant: `docs/build/META.md#database-migrations`
- Data docs: `docs/operations/data-catalogue/`, `docs/operations/data-lineage/`
- Migration runner: `packages/db/migrate.sh`
- Local test map: `tests/README.md`

## Rules

- Add schema changes as numbered migrations. Do not hand-apply SQL with `psql`.
- Apply migrations through `make migrate` or `packages/db/migrate.sh`.
- Keep migrations forward-only unless a work order explicitly defines rollback behavior.
- Update shared SQLAlchemy models or query code in the same changeset when the schema contract changes.
- Update data catalogue and lineage docs for table/column semantics.
- Production migrations are manual and reviewed; deploy automation only notifies.
