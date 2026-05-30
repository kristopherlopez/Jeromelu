# Docker Instructions

Read this before editing `docker/**`.

## Scope

`docker` owns local/prod Compose files and Caddy configuration.

## Required Context

- Production architecture: `docs/architecture/09-aws-architecture.md`
- CI/CD deploy docs: `docs/ops/ci-cd.md`
- Local connection notes: `docs/operations/local-dev-connections.md`
- Deploy script: `scripts/lightsail-deploy.sh`

## Rules

- Keep prod Compose aligned with the documented Lightsail topology.
- Do not add secrets directly to Compose or Caddy files.
- Be careful with published ports, health checks, volumes, and container names; scripts and runbooks may depend on them.
- If prod service names or exposed ports change, update deploy scripts, runbooks, and API/web configuration references.
- Caddy changes should preserve `jeromelu.ai` and `api.jeromelu.ai` routing unless the work order explicitly changes domains.
