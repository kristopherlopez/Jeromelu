---
tags: [area/operations, data-lineage]
---

# Lineage: miner_candidates

[Schema: data-catalogue/miner_candidates.md](../data-catalogue/miner_candidates.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Miner discovery loop | — (no S3 archive — agent-internal) | **Primary** — Miner agent writes here as it hunts the web for new NRL channels and videos |

Miner uses YouTube API + web tools (per [[project_miner_architecture]]) to discover candidates. The fetched payloads are not archived to S3 — only the resulting candidate row, with `metadata_json` carrying discovery-time enrichment (subs, view_count, published_at).

## Writers

- `services/api/app/miner/source_discovery/agent.py` — Source Discovery loop; INSERTs candidates with `status='pending'`
- `services/api/app/miner/youtube/client.py` — YouTube API enrichment (subscribers, view counts)
- **Admin review queue** — humans approve/reject via the admin UI; approval triggers promotion to [channels](channels.md) (kind=channel) or [sources](sources.md) (kind=video) and sets `promoted_channel_id`

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `id` | derived | UUID, DB-side default |
| `kind` | Miner | `channel` or `video` |
| `platform` | Miner | Defaults `youtube`; mirrors `channels.platform` |
| `external_id` | Miner | YouTube channel_id or video_id |
| `url`, `title`, `description` | Miner (YouTube API) | |
| `channel_external_id` | Miner | For videos: parent channel's external id |
| `content_categories` | Miner | LLM-classified: `match`, `analysis`, `news`, `injury`, `tactical`, etc. |
| `score` | Miner | Agent's own qualitative 0..1 |
| `score_reasons` | Miner | Free-text reasons (e.g. "Australian focus", "10k+ subs") |
| `metadata_json` | Miner (YouTube API) | Discovery-time enrichment |
| `discovered_via` | Miner | Query string OR `related-to:<channel_id>` OR `manual` |
| `discovered_at` | derived | DB default `now()` |
| `status` | review queue | `pending` → `approved`/`rejected`/`snoozed`/`duplicate` |
| `reviewed_at`, `reviewed_by`, `reviewed_note` | review queue | Human review metadata |
| `promoted_channel_id` | review queue | FK to channels; set on approve |
| `run_id` | Miner | Groups candidates from one Miner run (joins to `agent_runs.run_id`) |

## Notes

- Distinct from [sources](sources.md) so unapproved noise does not pollute the main pipeline.
- Renamed from `discovered_sources` in mig 035 per the agent-prefixed table-naming convention ([[feedback_agent_table_naming]]).
- Approval is a **promotion** — a row in `miner_candidates` becomes a row in `channels` or `sources`, not a side-effect copy.
