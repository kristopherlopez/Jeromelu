# API Instructions

Read this before editing `services/api/**`. Root `AGENTS.md` and `docs/build/META.md` still apply.

## Scope

`services/api` is the FastAPI boundary. Keep request/response contracts explicit, keep DB/API datetimes timezone-aware, and keep heavyweight ML dependencies out of import paths used by the API container and unit-test collection.

## Required Context

- API entrypoint: `services/api/app/main.py`
- Shared DB/session/types: `packages/shared/jeromelu_shared/`
- Tests: `tests/unit/api/` and relevant `tests/integration/`
- Code principles: root `AGENTS.md`
- Invariants: `docs/build/META.md`

## Rules

- Put imports at module top unless guarding a genuine optional dependency.
- Keep pure helpers split from heavy runtime modules when a feature needs ML, media, or external clients.
- Use Pydantic models or typed response shapes for API/data boundaries.
- Do not make API code depend on GPU-only packages such as `torch`, `pyannote`, or `insightface`.
- Add or update mirrored tests under `tests/unit/api/` for pure behavior.
- If a route changes public behavior, update the relevant `docs/pages/`, `docs/architecture/api-surface.md`, or subsystem docs.

## Special Cases

- Scout capture code has additional rules in `app/scout/AGENTS.md`.
- Voice, face, speaker-ID, and similar ML-heavy work must preserve the heavy-dependency isolation rule in `docs/build/META.md`.
