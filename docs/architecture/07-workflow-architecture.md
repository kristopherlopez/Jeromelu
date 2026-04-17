# Workflow Architecture

Implementation of each workflow lives in [`docs/agents/system/`](../agents/system/README.md). This doc describes intent; the agent pages describe what's actually built and which worker owns it.

## Core Scheduled Workflows

### Daily Intel Sweep
- check all approved sources
- ingest new content
- extract claims / predictions
- refresh consensus
- publish notable feed events

### Match Review Workflow
- collect match outcomes
- compare against predictions
- publish hits / misses
- update expert accuracy

### Strategy Refresh Workflow
- rebuild candidate player board
- refresh plans
- detect changed assumptions
- publish internal thought updates

### Weekly Decision Workflow
- lock on team state
- generate decision options
- score options via heuristics
- optionally allow safe contrarian override
- publish final move
- log immutable decision event

## Event-Triggered Workflows
- breaking injury news
- late team changes
- source publishes urgent claim
- operator injects event

These trigger partial re-evaluation, not full system recomputation unless required.
