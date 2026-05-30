---
tags: [area/operations, data-lineage]
---

# Lineage: sources

[Schema: data-catalogue/sources.md](../data-catalogue/sources.md)

## Sources (the upstream kind)

| Pipeline | Profile | Role |
|---|---|---|
| YouTube Data API (videos / playlists) | — | **Primary** — video discovery from approved channels |
| Miner candidate promotion (kind=video) | — | Direct video ingestion via candidate approval |
| Manual ingestion | — | One-off web articles, podcasts |

## Writers

- `services/api/app/miner/youtube/refresh.py` — periodic channel polling discovers new videos; INSERTs `sources` rows with `ingestion_status='pending'`; audited as Miner pipeline `youtube-refresh-videos` for the all-channel daily job and `youtube-channel-videos` for per-channel/backfill runs
- **Admin approval** — when a [miner_candidates](miner_candidates.md) row with `kind='video'` is approved, it promotes into a `sources` row
- `scripts/data/bulk_ingest_raw.py` / `scripts/data/reimport_from_s3.py` — bulk one-shot ingestion paths
- Transcript pipeline — sets `ingestion_status` and `ingested_at` after document download

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `source_id` | derived | UUID, DB-side default |
| `channel_id` | scope | FK → channels |
| `source_type` | writer | `youtube`, `podcast`, `web`, `radio`, `manual` |
| `title` | YouTube API / promotion | |
| `description` | YouTube API (mig 033) | Full description; chapter timestamps often embedded here |
| `thumbnail_url` | YouTube API (mig 033) | Best available (high/maxres for YouTube, cover art for podcast) |
| `duration_seconds` | YouTube API (mig 033) | Constant per video; refreshed on stats sync |
| `is_short` | derived | **Generated column** — `duration_seconds < 60`. True for YouTube Shorts |
| `creator_name` | promotion / manual | |
| `canonical_url` | promotion | UNIQUE; the single shareable URL |
| `approved_flag` | manual | Gates ingestion; defaults `false` |
| `ingestion_status` | Miner media acquisition | `pending`, `collected`, `failed`; `completed` remains for legacy caption-era rows |
| `transcription_status` | Analyst transcription | `NULL`, `transcribed`, `failed` |
| `audio_s3_key` | Miner media acquisition | Populated when `ingestion_status='collected'` |
| `extraction_method` | Analyst / legacy caption path | `deepgram_v1`, `deepgram_words+pyannote_v1`, `youtube_captions`, or `NULL` |
| `published_at` | YouTube API | Original publish timestamp |
| `ingested_at` | transcript pipeline | When the document was successfully fetched |
| `created_at` | derived | DB default `now()` |

## Notes

- Time-series popularity (views, likes, comments) lives separately in [video_metrics](video_metrics.md).
- Transcript and document content live in [source_documents](source_documents.md).
- Miner source health (`app.miner.source_health`) reads approved YouTube source status fields to count pending audio, collected-but-untranscribed sources, audio/transcription failures, and legacy `youtube_captions` rows that may need canonical re-extraction.
