---
tags: [area/operations, data-catalogue]
---

# miner_candidates

[← Data Catalogue](README.md) · [Lineage](../data-lineage/miner_candidates.md) · Layer 3 — Content & claims

Miner's candidate inbox. Miner (the source-discovery agent) writes here as it hunts the web for new NRL channels and videos worth onboarding. Humans approve / reject via the admin review queue; approval promotes a row into the canonical [channels](channels.md) (kind=channel) or [sources](sources.md) (kind=video) tables.

Distinct from `sources` so unapproved noise does not pollute the main pipeline. Renamed from `discovered_sources` in migration 035.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| kind | text | no | | `channel`, `video` |
| platform | text | no | `youtube` | Mirrors `channels.platform` |
| external_id | text | no | | YouTube channel_id or video_id |
| url | text | no | | |
| title | text | no | | |
| description | text | yes | | |
| channel_external_id | text | yes | | For videos: parent channel's external id |
| content_categories | text[] | no | {} | `match`, `analysis`, `news`, `injury`, `tactical`, `opinion`, `player-content`, `classic`, `rules-officiating`, `supercoach`, `nrlw`, `origin`, `international`, `junior` |
| score | numeric | yes | | Miner's qualitative score 0..1 |
| score_reasons | jsonb | no | [] | Free-text reasons (e.g. "Australian focus", "10k+ subs") |
| metadata_json | jsonb | no | {} | Discovery-time enrichment (subs, view_count, published_at, etc.) |
| discovered_via | text | no | | Query string OR `related-to:<channel_id>` OR `manual` |
| discovered_at | timestamptz | no | now() | |
| status | text | no | `pending` | `pending`, `approved`, `rejected`, `snoozed`, `duplicate` |
| reviewed_at | timestamptz | yes | | |
| reviewed_by | text | yes | | |
| reviewed_note | text | yes | | |
| promoted_channel_id | UUID | yes | | FK → channels; set when status flips to `approved` |
| run_id | text | yes | | Groups all candidates from one Miner run |

**Unique:** (platform, kind, external_id)
**Indexes:** status, kind, run_id, discovered_at DESC
**FK:** promoted_channel_id → channels.channel_id
