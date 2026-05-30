---
tags: [area/operations, data-lineage]
---

# Lineage: channels

[Schema: data-catalogue/channels.md](../data-catalogue/channels.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Miner candidate promotion | — | **Primary** — most rows arrive via `miner_candidates` → approve → promote |
| Manual seed (`data/sources.yaml`) | — | Local-dev convenience; not authoritative ([[project_sources_yaml_status]]) |

## Writers

- **Admin approval** — when a [miner_candidates](miner_candidates.md) row with `kind='channel'` is approved, it promotes into a `channels` row and `miner_candidates.promoted_channel_id` is set
- `services/api/app/miner/youtube/refresh.py` — `last_polled_at` updates on each refresh sweep
- Manual / admin endpoints — for editing slug, quality_rating, tags, active flag

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `channel_id` | derived | UUID, DB-side default |
| `slug` | promotion / manual | UNIQUE; URL-safe slug |
| `platform` | promotion | `youtube`, `podcast`, `website`, `twitter`, `instagram` |
| `external_id` | promotion | Platform-native id (YouTube channel id, podcast feed url, etc.); UNIQUE with platform |
| `name` | promotion | |
| `url` | promotion | |
| `description` | promotion | |
| `quality_rating` | manual | Defaults `5`; editable |
| `tags` | manual | Free-form tag set |
| `active` | manual | Defaults `true` |
| `logo_url` | promotion (mig 025) | YouTube avatar / channel logo |
| `handle` | promotion (mig 033) | YouTube `@customUrl`, Twitter `@handle` |
| `last_polled_at` | refresh sweep | Updated when video discovery polls this channel |
| `created_at` | derived | DB default `now()` |

## Notes

- Time-series popularity (subscribers, video count, total views) lives separately in [channel_metrics](channel_metrics.md).
- `data/sources.yaml` is interim — DB is system of record per [[project_sources_yaml_status]].
