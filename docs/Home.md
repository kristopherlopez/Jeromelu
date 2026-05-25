---
tags: [area/root]
aliases: [Index, Vault Home, Docs]
---

# Jaromelu Docs

This is the vault entry point. The docs cover Jaromelu — an autonomous AI commentator on the NRL, with SuperCoach gameplay layered on top from V2. Everything here is plain markdown; the same files are read by GitHub and Claude Code, so links use `[text](path.md)` (not `[[wikilinks]]`).

> Conventions for this vault — tags, link style, status taxonomy — live in [_vault-conventions](_vault-conventions.md).

## Start Here

- **What we're building** — [Venture Thesis](vision/01-venture-thesis.md)
- **Design language** — [Concepts](concepts/README.md)
- **Agents (crew, system, skills)** — [Agents](agents/README.md)
- **The five canonical pages** — Feed, Wiki, Analysis, Ledger, Pulse, Ask Me — see [pages/](pages/)

## Vision

The strategy spine — what Jaromelu is and why. Start here.

1. [Venture Thesis](vision/01-venture-thesis.md)
2. [The Show](vision/02-the-show.md)
3. [Knowledge Asset](vision/03-knowledge-asset.md)
4. [The Machine](vision/04-the-machine.md)

## Architecture

How it's built. Its own 01–09 series.

1. [Information Architecture](architecture/01-information-architecture.md)
2. [Runtime Architecture](architecture/02-runtime-architecture.md)
3. [LLM Architecture](architecture/03-llm-architecture.md)
4. [Workflow Architecture](architecture/04-workflow-architecture.md)
5. [Explainability & Governance](architecture/05-explainability-and-governance.md)
6. [V1 Scope & Roadmap](architecture/06-v1-scope-and-roadmap.md)
7. [C4 System Blueprint](architecture/07-c4-system-blueprint.md)
8. [Technology Stack](architecture/08-technology-stack.md)
9. [AWS Architecture](architecture/09-aws-architecture.md)

## Agents

| Layer | Index |
|---|---|
| **Crew** — internal reasoning composing Jaromelu | [crew/README](agents/crew/README.md) |
| **System** — Temporal workers, LLM activities, scrapers | [system/README](agents/system/README.md) |
| **Skills** — Claude Code dev-time skills | [skills/README](agents/skills/README.md) |

## Pages (Product Surfaces)

| Page | Overview |
|---|---|
| Feed | [pages/feed/overview](pages/feed/overview.md) |
| Wiki | [pages/wiki/overview](pages/wiki/overview.md) |
| Analysis | [pages/analysis/overview](pages/analysis/overview.md) |
| Ledger | [pages/ledger/overview](pages/ledger/overview.md) |
| Pulse | [pages/pulse/overview](pages/pulse/overview.md) |
| Ask Me | [pages/ask-me/overview](pages/ask-me/overview.md) |

## Operations

- [Local Dev Connections](operations/local-dev-connections.md)
- [AWS Setup Guide](operations/aws-setup-guide.md)
- [IaC Overview](operations/iac-overview.md) · [Migration Plan](operations/iac-migration-plan.md) · [Runbook](operations/iac-runbook.md)
- [Data Catalogue](operations/data-catalogue/README.md)

## Other Areas

- [Sources](sources/README.md) — external content ingestion
- [Avatar](avatar/README.md) — Jaromelu's on-screen presence
- [Design System](design-system/theme-and-style.md) · [UI/UX Brief](design-system/ui-ux-brief.md)
- [Todo / Backlog](todo/TODO.md)
- [Archive](archive/) — historical specs

## Live Dashboards

Powered by Dataview — install Dataview first (see [_obsidian-setup](_obsidian-setup.md)).

- [System Agent Status](_dashboards/system-status.md) — what's live, partial, skeleton, not built
- [Backlog](_dashboards/backlog.md) — designed-but-not-built + planning items
- [Coverage by Area](_dashboards/by-area.md) — doc count per area, recent + stalest
- [Agents Kanban](_dashboards/agents-kanban.md) — drag-and-drop status board (requires Kanban plugin)
- [Project Home](_dashboards/Project%20Home.canvas) — visual canvas dashboard

### Quick status board (inline)

```dataview
TABLE WITHOUT ID
  file.link AS "Agent",
  filter(file.tags, (t) => startswith(t, "#status/"))[0] AS "Status"
FROM "agents/system"
WHERE file.name != "README"
SORT file.name ASC
```

## Useful Searches (Obsidian)

- `tag:#status/skeleton` — what's stubbed but not built
- `tag:#status/not-built` — what's still on paper
- `tag:#area/agents` — everything agent-related
- `tag:#status/planning` — backlog items

## Setup

First time opening this vault on a new machine? Run through [_obsidian-setup](_obsidian-setup.md). Conventions live in [_vault-conventions](_vault-conventions.md).
