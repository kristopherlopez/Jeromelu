---
tags: [area/operations, data-catalogue]
---

# channels

[← Data Catalogue](README.md) · [Lineage](../data-lineage/channels.md) · Layer 3 — Content & claims

Registry of content sources (YouTube channels, podcast feeds, websites).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| channel_id | UUID | PK | uuid4 | |
| slug | text | no | | unique |
| platform | text | no | | `youtube`, `podcast`, `website`, `twitter`, `instagram` |
| external_id | text | yes | | unique with platform |
| name | text | no | | |
| url | text | yes | | |
| description | text | yes | | |
| quality_rating | int | no | 5 | |
| tags | text[] | no | [] | |
| active | bool | no | true | |
| logo_url | text | yes | | Channel avatar / logo (mig 025) |
| handle | text | yes | | Platform handle — YouTube `@customUrl`, Twitter `@handle` (mig 033) |
| last_polled_at | timestamptz | yes | | |
| created_at | timestamptz | no | now() | |

**Indexes:** platform, active, handle (partial: WHERE handle IS NOT NULL)
**Unique:** slug; (platform, external_id)
