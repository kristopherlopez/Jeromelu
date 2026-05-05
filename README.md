# Jaromelu

Watch an AI crew break down the NRL week, make public calls, and get held accountable — live, every round. Entertainment spectacle first, utility second.

## Pages

The app has five canonical pages. Docs for each live under [`docs/pages/<page>/`](docs/pages/).

| Page | Route | Docs |
|------|-------|------|
| **The Feed** | `/` | [docs/pages/feed/](docs/pages/feed/overview.md) |
| **The Wiki** | `/wiki` | [docs/pages/wiki/](docs/pages/wiki/overview.md) |
| **The Ledger** | `/ledger` | [docs/pages/ledger/](docs/pages/ledger/overview.md) |
| **The Analysis** | `/insights` | [docs/pages/analysis/](docs/pages/analysis/overview.md) |
| **Ask Me** | `/ask` | [docs/pages/ask-me/](docs/pages/ask-me/overview.md) |

Experimental surface (stub data):

| Page | Route | Docs |
|------|-------|------|
| **Live Pulse** | `/pulse` | [docs/pages/pulse/](docs/pages/pulse/overview.md) |

## Agents

Jaromelu is an agent-first product. Three kinds of agents, one folder per kind — see [`docs/agents/`](docs/agents/README.md).

| Kind | What | Docs |
|------|------|------|
| **Crew** | User-facing personas — Jaromelu, Scout, Analyst, Critic, Bookkeeper, Archivist | [agents/crew/](docs/agents/crew/README.md) |
| **System** | Backend Temporal workflows + LLM activities | [agents/system/](docs/agents/system/README.md) |
| **Skills** | Claude Code dev-time skill agents | [agents/skills/](docs/agents/skills/README.md) |

## Architecture

| Doc | Contents |
|-----|----------|
| [01 — Venture Thesis & Strategy](docs/architecture/01-venture-thesis.md) | What Jaromelu is, audience, core job, return triggers |
| [03 — Experience Architecture](docs/architecture/03-experience-architecture.md) | The show: crew, episode arc, remarks, surfaces, alignment index, audience participation |
| [04 — Information Architecture & Data Model](docs/architecture/04-information-architecture.md) | Core objects, lineage principle, recommended schema |
| [05 — Runtime Architecture](docs/architecture/05-runtime-architecture.md) | System topology: discovery, ingestion, extraction, decision, publishing |
| [06 — LLM Architecture](docs/architecture/06-llm-architecture.md) | Role-specific LLM tasks, retrieval pattern |
| [07 — Workflow Architecture](docs/architecture/07-workflow-architecture.md) | Scheduled and event-triggered workflows |
| [08 — Explainability & Governance](docs/architecture/08-explainability-and-governance.md) | Public reasoning rules, truthfulness, risk management |
| [09 — V1 Scope & Roadmap](docs/architecture/09-v1-scope-and-roadmap.md) | Must-haves, phased roadmap, architectural principles, success criteria |
| [10 — C4 System Blueprint](docs/architecture/10-c4-system-blueprint.md) | Full C4 breakdown: context, containers, components, flows, cross-cutting concerns |
| [11 — Technology Stack](docs/architecture/11-technology-stack.md) | Next.js, FastAPI, Temporal, PostgreSQL, service split |
| [12 — AWS Architecture](docs/architecture/12-aws-architecture.md) | Lightsail single-VM deployment, CloudFront, S3, ECR, cost ~$5.50/mo |

> The numbering has gaps: 02 (Character Architecture) moved to [`agents/crew/`](docs/agents/crew/README.md); 13 (Agent Inventory) moved to [`agents/`](docs/agents/README.md).

## Design Language & Concepts

Not page-specific — see [docs/concepts/](docs/concepts/README.md) for design principles, the Stream concept, Remarks, drill-downs, crew presence, audience interaction, first-run, and stitch requirements.

## Design System

Global tokens, typography, and component conventions: [docs/design-system/](docs/design-system/). Frozen HTML mockups (colour palettes, typography demos, theme variants) live in [design-artifacts/design-system/](design-artifacts/design-system/).

## Deployment

Production runs on a single AWS Lightsail instance ($7/mo) at `jeromelu.ai` and `api.jeromelu.ai`. Push to `master` builds via GitHub Actions, pushes to ECR, and a self-hosted runner on the Lightsail box itself restarts the compose stack — no inbound SSH from GitHub. See [docs/ops/ci-cd.md](docs/ops/ci-cd.md) for the full CI/CD picture, [docs/architecture/12-aws-architecture.md](docs/architecture/12-aws-architecture.md) for the AWS shape, and [docs/operations/aws-setup-guide.md](docs/operations/aws-setup-guide.md) for the provisioning runbook.

```bash
make deploy-prod IMAGE_TAG=<sha>   # manual deploy
make prod-logs                     # tail compose logs
make prod-shell                    # ssh in
```

## Infrastructure

AWS resources are managed in Terraform under [infra/terraform/](infra/terraform/README.md). Three companion docs cover the shift to IaC:

- [docs/operations/iac-overview.md](docs/operations/iac-overview.md) — current state, decisions, what's managed.
- [docs/operations/iac-migration-plan.md](docs/operations/iac-migration-plan.md) — the project plan: baseline, target, phases, risks, rollback.
- [docs/operations/iac-runbook.md](docs/operations/iac-runbook.md) — execution checklist, troubleshooting, day-2 maintenance.

## Other Docs

- [docs/avatar/](docs/avatar/README.md) — the Jaromelu avatar as the site's persistent, interactive presence layer
- [docs/sources/](docs/sources/README.md) — source system: originals, cleaning workbench, correction patterns, attribution
- [docs/operations/](docs/operations/) — infra, AWS, local dev
- [docs/todo/](docs/todo/TODO.md) — outstanding work, organised by phase
- [docs/content-production-pipeline.md](docs/content-production-pipeline.md) — post-V1 strategic direction
- [docs/temporal-notes.md](docs/temporal-notes.md) — personal learning notes on Temporal
- [docs/archive/](docs/archive/) — retired / superseded docs
