# 2.1 Decision Worker

**Phase:** 2 — Prove the Character (Personality + Experience)
**Priority:** 7 — Jerome starts making moves
**Service:** `services/worker-decision`

## Tasks
- [ ] Rule-based decision engine — transparent heuristics, no black box
- [ ] Candidate move generator — enumerate viable trades, captain picks, structure changes
- [ ] Move scoring via heuristics (consensus signals, matchup data, squad constraints)
- [ ] Move ranking and selection
- [ ] Rationale generation — explain why each decision was made
- [ ] Policy-bounded contrarian override system
- [ ] Squad state management — track current team, trades remaining, budget
- [ ] Strategic planning — round-by-round plans with scenario modeling
- [ ] Assumption invalidation detection — detect when plans need rebuilding
- [ ] Temporal workflows: `WeeklyDecisionWorkflow`, `StrategyRefreshWorkflow`
