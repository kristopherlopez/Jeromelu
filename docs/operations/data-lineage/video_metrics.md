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

- `services/api/app/scout/youtube/client.py` — sampled at video discovery time and daily thereafter via the admin refresh endpoint; INSERTs one row per video per sample

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `metric_id` | derived | UUID, DB-side default |
| `source_id` | scope | FK → sources (CASCADE) |
| `sampled_at` | derived | DB default `now()`; UNIQUE with source_id |
| `source` | refresher | `youtube_api`, `manual`, ... |
| `metrics` | refresher (raw API slice) | Platform-specific JSONB. YouTube: `{views, likes, comments, duration_seconds}` |

## Read pattern

For "current state" queries, prefer the `video_latest_metrics` view.

## Notes

- Same shape as [channel_metrics](channel_metrics.md). See migration 023 for the design rationale (identity stays clean in `sources`; popularity changes-over-time + varies-per-platform lives here).
