# Ingestion

| | |
|---|---|
| **Worker** | `services/worker-ingestion/app/main.py` |
| **Task Queue** | `ingestion` |
| **Crew counterpart** | [Scout](../crew/scout.md) |

---

## IntelSweepWorkflow

| | |
|---|---|
| **Workflow** | `services/worker-ingestion/app/workflows/intel_sweep.py` |
| **Schedule** | Daily 10 PM AEST |
| **Purpose** | Content ingestion pipeline: discover new videos on whitelisted channels, fetch transcripts to S3, index `Source` + `SourceDocument` to DB |

**Steps:**
1. `discover_new_videos` — poll channels, deduplicate by watermark
2. For each new video:
   - `collect_transcript` — fetch via YouTube API, store JSON in S3
   - `index_document` — write Source + SourceDocument rows

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
