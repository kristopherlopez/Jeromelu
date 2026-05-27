---
tags: [area/operations, data-catalogue]
---

# video_metrics

[← Data Catalogue](README.md) · [Lineage](../data-lineage/video_metrics.md) · Layer 3 — Content & claims

Time-series popularity per video (a [sources](sources.md) row). Same shape as [channel_metrics](channel_metrics.md) — see migration 023 for the design rationale. YouTube payload: `{views, likes, comments, duration_seconds}`. Sampled at video discovery time and daily thereafter via the admin refresh endpoint.

**Change-only storage (migration 070).** The daily refresh records a row **only when the payload changed** vs the video's latest snapshot — ~70% of daily samples are byte-identical and are skipped. Consequences for readers:

- The latest row's `sampled_at` means **last *changed***, not last *checked*. To answer "was this re-confirmed today?" use the last successful daily refresh run (cron-report / the refresh job's `agent_runs` row), **not** this table.
- The `video_latest_metrics` view still returns the current value — the last change *is* the current state.
- Velocity reads must use **as-of-cutoff** semantics (most-recent row ≤ a cutoff date), never "the row at exactly N days ago" — gaps between rows are expected and meaningful (no row = no change).

One-time disk reclaim of the pre-migration bloat is a manual `VACUUM (FULL)` — see the [metrics dedup runbook](../metrics-dedup-runbook.md).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| metric_id | UUID | PK | uuid4 | |
| source_id | UUID | no | | FK → sources (CASCADE) |
| sampled_at | timestamptz | no | now() | |
| source | text | no | | `youtube_api`, `manual`, ... |
| metrics | jsonb | no | {} | Platform-specific shape |

**Unique:** (source_id, sampled_at)
**Indexes:** (source_id, sampled_at DESC), sampled_at DESC

For "current state" queries prefer the `video_latest_metrics` view.
