---
tags: [area/operations, data-lineage]
---

# Lineage: video_metrics

[Schema: data-catalogue/video_metrics.md](../data-catalogue/video_metrics.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| YouTube Data API (videos resource) | — | **Primary** for YouTube videos |

## Writer

- `services/api/app/scout/youtube/client.py` (called by `services/api/app/scout/youtube/refresh.py`) — sampled at video discovery time and daily thereafter via the admin refresh endpoint; INSERTs a row **only when views/likes/comments change** vs the latest snapshot (change-only storage, migration 070). First-snapshot writers (`refresh_channel_videos`, including approval-time `youtube-channel-videos` runs) always write — no prior row to compare. Daily all-video refreshes are audited as Scout pipeline `youtube-refresh-videos`.

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `metric_id` | derived | UUID, DB-side default |
| `source_id` | scope | FK → sources (CASCADE) |
| `sampled_at` | derived | DB default `now()`; UNIQUE with source_id |
| `source` | refresher | `youtube_api`, `manual`, ... |
| `metrics` | refresher (raw API slice) | Platform-specific JSONB. YouTube: `{views, likes, comments, duration_seconds}` |

## Read pattern

For "current state" queries, prefer the `video_latest_metrics` view. Velocity/breakout reads must use **as-of-cutoff** semantics (the most-recent row ≤ a cutoff date), never assume a row exists at an exact prior date — under change-only storage, gaps between rows are expected (a gap means "unchanged").

## Notes

- Same shape as [channel_metrics](channel_metrics.md). See migration 023 for the design rationale (identity stays clean in `sources`; popularity changes-over-time + varies-per-platform lives here).
