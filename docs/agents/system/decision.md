---
tags: [area/agents, subarea/system, status/not-built]
---

# Decision

| | |
|---|---|
| **Worker** | `services/worker-decision/` (skeleton only) |
| **Task Queue** | `decision` |
| **Status** | Not yet built |
| **Crew counterparts** | [Jaromelu](../crew/jaromelu.md) (the call), [Critic](../crew/critic.md) (challenge layer), [Archivist](../crew/archivist.md) (historical context) |

## Purpose (intended)

Rule-based decision engine — transparent heuristics, no black box. Generates candidate moves (trades, captain picks, structural changes), scores them with heuristics, ranks, and produces rationale.

Envisioned workflows:
- `WeeklyDecisionWorkflow` — run weekly to produce the round's moves
- `StrategyRefreshWorkflow` — rebuild plans when assumptions invalidate

## Related

- Phase 2.1 tasks: [`../../todo/TODO.md`](../../todo/TODO.md#21-decision-worker-servicesworker-decision)
