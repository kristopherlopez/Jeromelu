---
tags: [area/operations, data-catalogue]
---

# channel_metrics

[← Data Catalogue](README.md) · [Lineage](../data-lineage/channel_metrics.md) · Layer 3 — Content & claims

Time-series popularity per channel. Multi-platform via the JSONB `metrics` column — YouTube uses `{subscribers, videos, views, country, channel_published_at}`; other platforms (podcast, twitter) carry their own shape. Identity stays clean in [channels](channels.md); popularity (which changes over time and varies per platform) lives here.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| metric_id | UUID | PK | uuid4 | |
| channel_id | UUID | no | | FK → channels (CASCADE) |
| platform | text | no | | Mirrors `channels.platform` at sample time |
| sampled_at | timestamptz | no | now() | |
| source | text | no | | `youtube_api`, `apple_podcasts`, `manual`, ... |
| metrics | jsonb | no | {} | Platform-specific shape |

**Unique:** (channel_id, sampled_at)
**Indexes:** (channel_id, sampled_at DESC), (platform, sampled_at DESC), sampled_at DESC

For "current state" queries (wiki cards, ranking) prefer the `channel_latest_metrics` view over scanning the table.

**Change-only storage (migration 070).** Like [video_metrics](video_metrics.md), the daily refresh records a row **only when the payload changed** vs the channel's latest snapshot. The latest row's `sampled_at` means last *changed*, not last *checked* (freshness derives from the last successful refresh run, not this table); `channel_latest_metrics` still returns the current value; velocity reads must use as-of-cutoff semantics, not an exact prior date.
