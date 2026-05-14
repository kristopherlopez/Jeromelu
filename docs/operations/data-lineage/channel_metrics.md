---
tags: [area/operations, data-lineage]
---

# Lineage: channel_metrics

[Schema: data-catalogue/channel_metrics.md](../data-catalogue/channel_metrics.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| YouTube Data API (channels resource) | — (responses not S3-archived today) | **Primary** for YouTube |
| Future: Apple Podcasts API, Twitter API | — | Per-platform writers when those channels are added |

## Writer

- `services/api/app/scout/youtube_api.py` (called by `services/api/app/scout/refresh.py`) — periodic refresh against YouTube Data API; INSERTs one row per channel per sample with the platform-specific JSONB `metrics` blob

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `metric_id` | derived | UUID, DB-side default |
| `channel_id` | scope | FK → channels (CASCADE) |
| `platform` | refresher | Mirrors `channels.platform` at sample time |
| `sampled_at` | derived | DB default `now()`; UNIQUE with channel_id |
| `source` | refresher | `youtube_api`, `apple_podcasts`, `manual`, ... |
| `metrics` | refresher (raw API response slice) | Platform-specific JSONB. YouTube: `{subscribers, videos, views, country, channel_published_at}` |

## Read pattern

For "current state" queries (wiki cards, ranking, etc.), prefer the `channel_latest_metrics` view rather than scanning the full table.
