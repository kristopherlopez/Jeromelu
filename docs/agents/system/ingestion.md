---
tags: [area/agents, subarea/system, status/live]
---

# Audio Ingestion (Scout § 3.5)

| | |
|---|---|
| **Module** | `services/api/app/scout/media/audio.py` |
| **Driver** | `python -m app.scout.media.audio_cli <source_id>` · `make collect-audio SOURCE_ID=<uuid>` |
| **Crew counterpart** | [Scout](../crew/scout/README.md) — this is Scout's audio-pull surface (§3.5). |
| **ETL role** | **Extract only.** Pulls audio bytes via yt-dlp and persists to S3. No interpretation. |
| **Status** | Single-source CLI shipped. Recurring drain job not yet built. |

Replaces the legacy Temporal-based `IntelSweepWorkflow` (under `services/worker-ingestion/`, dev-only). Sits at the boundary between Scout's discovery + enumeration surface and Analyst's transcription surface.

> **For transcription / diarisation** — see [transcription-pipeline.md](transcription-pipeline.md). That's a separate Analyst-owned pass that runs on Scout's audio after it's in S3.

---

## What it does

For one approved-but-pending YouTube source:

1. Resolve `video_id` from `source.canonical_url`.
2. `yt-dlp` audio-only download (m4a, ~96 kbps) to a temp dir.
3. Upload to `s3://jeromelu-raw-audio/youtube/{channel_id}/{video_id}.m4a`. Idempotent — skipped if the S3 object already exists.
4. Write back: `sources.audio_s3_key`, `sources.ingestion_status='collected'`.

That's it. No Deepgram, no DB writes beyond the source row. Cost per source: $0 (yt-dlp + S3 storage rounding to noise).

On failure (yt-dlp DownloadError, video deleted, members-only): `sources.ingestion_status='failed'`, `AudioError` raised. Operator inspects and re-runs.

---

## Hand-off contract

| Table | Fields written | Fields left for downstream |
|---|---|---|
| `sources` | `audio_s3_key`, `ingestion_status='collected'` | `transcription_status`, `extraction_method`, `ingested_at` (Analyst sets these once the transcript materialises) |

Scout writes **nothing** to `source_documents`, `source_speakers`, `source_chunks`. Those are Analyst's writes — see [transcription-pipeline.md](transcription-pipeline.md).

---

## Running

```bash
make collect-audio SOURCE_ID=<uuid>
```

The Make target sets `S3_ENDPOINT=''` (real AWS, not local MinIO — the audio bucket only exists on AWS) and `PYTHONPATH=services/api`.

Expected output:

```
OK
  audio_s3_key:    youtube/<channel>/<vid>.m4a
  bytes_uploaded:  43,742,310
```

Or, if the audio is already in S3 (re-run / idempotent):

```
OK
  audio_s3_key:    youtube/<channel>/<vid>.m4a
  bytes_uploaded:  (skipped — already in S3)
```

---

## Backlog

- **Recurring drain job** — APScheduler / cron over `ingestion_status='pending'`. Single-source CLI today.
- **Backfill of `source_chunks_v1`** — 215 prod sources still ingested under the legacy auto-caption path. Re-collect audio + transcribe via the new flow on highest-leverage channels first.
- **Member-only / paywalled video handling** — yt-dlp can't reach these. Options: cookies file, manual upload, or skip + log.

---

## Related

- [Scout — § 3.5 audio acquisition](../crew/scout/architecture.md#35-audio-acquisition-deterministic-shipped)
- [Transcription (Analyst)](transcription-pipeline.md) — what runs on Scout's audio next
- [Source discovery](source-discovery.md) — Scout's discovery + enumeration; produces the `sources` rows that this module drains
- [Sources § extraction method](../../sources/extraction-method.md) — full pipeline cost model
- [Migration 044](../../../packages/db/migrations/044_audio_first_extract.sql), [Migration 045](../../../packages/db/migrations/045_split_ingestion_transcription.sql), [Migration 046](../../../packages/db/migrations/046_chunk_paragraph_break.sql)
