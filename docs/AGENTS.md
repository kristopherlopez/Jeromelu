# Docs Instructions

Read this before editing `docs/**`.

## Scope

Docs are production code. Keep owner docs current, avoid duplicated rules, and preserve run reports as history.

## Required Context

- Documentation discipline: `docs/build/META.md`
- Vault conventions: `docs/_vault-conventions.md`
- Root README for top-level navigation: `README.md`

## Rules

- Update the owning source document first, then any domain summary that points to it.
- Do not rewrite historical run reports except to append clearly marked follow-up proof or correct factual errors.
- Keep completed build history in `docs/build/runs/`, not in active planning files.
- Update data catalogue, lineage, and source docs when schema or extractor mappings change.
- Keep page docs under `docs/pages/<page>/` aligned with user-facing route behavior.
- Prefer links to canonical docs over repeating long instructions.
