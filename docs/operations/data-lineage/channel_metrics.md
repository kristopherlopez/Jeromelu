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

- `services/api/app/scout/youtube/client.py` (called by `services/api/app/scout/youtube/refresh.py`) — periodic refresh against YouTube Data API; INSERTs a row **only when the metrics payload changes** vs the latest snapshot (change-only storage, migration 070). The recurring channel metrics endpoint is audited as Scout pipeline `youtube-channel-stats`. First-snapshot writers (channel-approval snapshot in `routers/recon.py`, `canonicalise_handles` backfill) always write — no prior row to compare.

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

For "current state" queries (wiki cards, ranking, etc.), prefer the `channel_latest_metrics` view rather than scanning the full table. Velocity reads must use as-of-cutoff semantics (most-recent row ≤ a cutoff), not an exact prior date — gaps are expected under change-only storage.
