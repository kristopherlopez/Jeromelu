---
tags: [area/operations, data-catalogue]
---

# video_metrics

[← Data Catalogue](README.md) · Layer 3 — Content & claims

Time-series popularity per video (a [sources](sources.md) row). Same shape as [channel_metrics](channel_metrics.md) — see migration 023 for the design rationale. YouTube payload: `{views, likes, comments, duration_seconds}`. Sampled at video discovery time and daily thereafter via the admin refresh endpoint.

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
