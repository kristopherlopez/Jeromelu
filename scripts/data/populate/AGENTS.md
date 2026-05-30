# Populate Script Instructions

Read this before editing `scripts/data/populate/**`.

## Scope

This package projects archived Scout S3 payloads into relational tables. It is the historical backfill driver and the home for per-table extractor logic.

## Required Context

- Package README: `scripts/data/populate/README.md`
- Dry-run invariant: `docs/build/META.md#populate_db_from_s3---dry-run--fixed-2026-05-24-phase-35--task-18`
- Tests: `tests/unit/scripts/data/populate/`
- Fixtures: `tests/fixtures/scout/`

## Rules

- Keep phases idempotent. Re-running the same inputs must not duplicate or corrupt rows.
- Preserve the `commit: bool = True` contract and guard every internal `db.commit()`.
- Keep pure extractor seams separate from S3/DB work so unit tests do not need IO.
- Use natural keys and UPSERTs for deterministic writes.
- Add or update fixture-backed tests for mapping changes.
- If a phase changes table semantics, update data catalogue and lineage docs.
- Do not use this package to refetch upstream data; it projects archived payloads.
