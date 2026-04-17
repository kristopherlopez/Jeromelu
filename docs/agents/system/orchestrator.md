# Orchestrator

| | |
|---|---|
| **Worker** | `services/worker-orchestrator/app/main.py` |
| **Task Queue** | `orchestrator` |
| **Status** | Skeleton — workflow list is empty; workflows currently registered directly by their activity workers |

## Purpose

Central hub that owns workflow definitions and coordinates distributed activity workers.

## Design Intent

Per [`../../todo/temporal-orchestration.md`](../../todo/temporal-orchestration.md), all workflow definitions should live in this worker. Activity workers would register only activities. This centralisation hasn't been completed yet — today each activity worker registers its own workflows.
