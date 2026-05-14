---
tags: [area/operations, data-catalogue]
---

# sources

[← Data Catalogue](README.md) · Layer 3 — Content & claims

Individual content items (a specific video, episode, article).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| source_id | UUID | PK | uuid4 | |
| channel_id | UUID | yes | | FK → channels |
| source_type | text | no | | `youtube`, `podcast`, `web`, `radio`, `manual` |
| title | text | no | | |
| description | text | yes | | Full video/article description; chapter timestamps often live here (mig 033) |
| thumbnail_url | text | yes | | Best available thumbnail (YouTube high/maxres, podcast cover art) (mig 033) |
| duration_seconds | int | yes | | Length in seconds; constant per video, refreshed on stats sync (mig 033) |
| is_short | bool | yes | | **Generated column** — `duration_seconds IS NOT NULL AND duration_seconds < 60`. True for YouTube Shorts (mig 033) |
| creator_name | text | yes | | |
| canonical_url | text | yes | | unique |
| approved_flag | bool | no | false | |
| ingestion_status | text | no | `pending` | |
| published_at | timestamptz | yes | | |
| ingested_at | timestamptz | yes | | |
| created_at | timestamptz | no | now() | |

**Indexes:** source_type, approved_flag, is_short (partial: WHERE is_short=true), duration_seconds (partial: WHERE NOT NULL)
**Unique:** canonical_url
**FK:** channel_id → channels.channel_id
