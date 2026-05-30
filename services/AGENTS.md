# Services Instructions

Read this before editing `services/**`.

## Scope

`services` contains runtime containers and app services. API, web, and GPU have local instructions. The worker service folders are legacy or future-facing unless an active work order says otherwise.

## Required Context

- Runtime architecture: `docs/architecture/02-runtime-architecture.md`
- Production topology: `docs/architecture/09-aws-architecture.md`
- CI/CD behavior: `docs/ops/ci-cd.md`
- Compose files: `docker/docker-compose.yml`, `docker/docker-compose.prod.yml`

## Rules

- Keep the production Lightsail stack lean: API, web, Postgres, Caddy, plus approved cron/container patterns.
- Do not introduce Temporal into production without explicit human sign-off.
- Keep service-specific dependencies inside the service that needs them.
- If a Dockerfile or runtime entrypoint changes, update deployment docs and relevant path filters if needed.
- API, web, and GPU edits must also follow their local `AGENTS.md`.
