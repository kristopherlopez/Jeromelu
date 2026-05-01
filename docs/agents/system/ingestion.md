---
tags: [area/agents, subarea/system, status/live]
---

# Ingestion

| | |
|---|---|
| **Worker** | `services/worker-ingestion/app/main.py` |
| **Task Queue** | `ingestion` |
| **Crew counterpart** | [Scout](../crew/scout.md) — this is Scout's transcript-pull surface (one component of Scout's broader Extract role) |
| **ETL role** | **Extract only.** Pulls raw transcripts and persists them as `source_documents` + `source_chunks`. No Transform. |

### Extract-only boundary

Per Scout's [ETL role](../crew/scout.md), this worker writes **raw transcript fields only**:

| Table | Fields written | Fields left NULL (for Transform downstream) |
|---|---|---|
| `source_documents` | `s3_key`, `raw_text`, `transcript_available`, `language`, `checksum`, `chunk_count` | `cleaned_text` |
| `source_chunks` | `raw_text`, `chunk_index`, `start_offset`, `end_offset`, `start_ts`, `end_ts` (preserves YouTube caption boundaries as-is) | `clean_text`, `embedding` |

It does not write `source_speakers` (diarisation — Deepgram pass), `source_chapters` (analyse-transcript pipeline), `source_annotations` (sentiment, mentions, themes), `quotes`, or `claims`. Those are all Transform stages downstream.

---

## IntelSweepWorkflow

| | |
|---|---|
| **Workflow** | `services/worker-ingestion/app/workflows/intel_sweep.py` |
| **Schedule** | Daily 10 PM AEST |
| **Purpose** | Discover new videos on whitelisted channels and pull their raw transcripts. Writes `Source` + `SourceDocument` (+ `source_chunks` at the original caption boundaries) to DB; raw JSON to S3. **Extract only — no cleaning, diarisation, or embedding.** |

**Steps:**
1. `discover_new_videos` — poll channels, deduplicate by watermark
2. For each new video:
   - `collect_transcript` — fetch via YouTube API, store raw JSON in S3
   - `index_document` — write `Source` + `SourceDocument` rows (raw fields only) and the per-caption `source_chunks` rows

**Retry policy:** 3 attempts, 5s initial interval, 2× backoff. Non-retryable: `RateLimitError`, `NoTranscriptFound`, `TranscriptsDisabled`.

**Returns:** `{discovered, collected, indexed, errors}`

---

## Ingestion Utilities

Scripts and endpoints that support the pipeline but aren't Temporal workflows:

| Utility | Location | Purpose |
|---|---|---|
| `backfill.py` | `services/worker-ingestion/app/` | One-time backfill: uses `yt-dlp` to discover ALL videos from whitelisted channels, collect transcripts, upload to S3, index in DB |
| `trigger_sweep.py` | `services/worker-ingestion/app/` | Manually trigger IntelSweepWorkflow (testing/debugging) |
| `seed_channels.py` | `services/worker-ingestion/app/` | Load channels from `sources.yaml` and upsert to DB |
| `POST /admin/ingest` | `services/api/app/routers/admin.py` | Ingest transcript + claims from S3 — creates Source, SourceDocument, SourceChunks, Claims, ClaimChunks with entity resolution |
| `POST /admin/ingest-raw` | `services/api/app/routers/admin.py` | Ingest raw transcript without claims |
| `GET /admin/pipeline` | `services/api/app/routers/admin.py` | View pipeline stage for every source (discovered → collected → indexed → cleaned → extracted) |
| `GET /admin/sync-status` | `services/api/app/routers/admin.py` | Cross-reference local files, S3, and DB for mismatches |

## Related

- Full workflow doc: [`daily-intel-sweep.md`](daily-intel-sweep.md)
- Tasks and architecture: [`../../todo/ingestion-worker.md`](../../todo/ingestion-worker.md)
