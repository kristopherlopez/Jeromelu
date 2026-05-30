# Web Instructions

Read this before editing `services/web/**`.

## Scope

`services/web` is the Next.js app. It owns user-facing pages, app shell components, page data modules, and local API routes.

## Required Context

- Design system: `docs/design-system/theme-and-style.md`, `docs/design-system/ui-ux-brief.md`
- Page docs: `docs/pages/<page>/`
- Frontend hardening backlog: `docs/operations/engineering-quality-hardening.md`
- Web README: `services/web/README.md` (currently generic; prefer the docs above for project-specific rules)

## Rules

- Use TypeScript and keep route/page data shapes explicit.
- Run or document `npm run typecheck` and `npm run lint` for web changes.
- Prefer existing app shell, theme tokens, and component conventions.
- Add `"use client"` only when browser state/effects/events require it.
- Keep fixed-format UI dimensions stable and prevent text overflow across mobile and desktop.
- If UI changes are substantial, use the UI review workflow or capture a browser screenshot before handoff.
- Public page behavior changes should update the matching `docs/pages/<page>/` doc.
