# 1.2 Ingestion Worker

**Phase:** 1 — Prove the Brain (Intelligence Layer)
**Priority:** 3 — Data in = everything else possible
**Service:** `services/worker-ingestion`

## Architecture

Single service with four Temporal activities. Split into separate services later if needed.

### Pipeline

| Activity | Responsibility |
|----------|---------------|
| **Discovery** | Poll channel RSS feeds for new video IDs. Watermark + checksum dedup to skip already-processed videos. |
| **Collection** | Fetch transcript via `youtube-transcript-api`. Store as structured JSON in S3. |
| **Processing** | Extract plain text from JSON segments. |
| **Indexing** | Write `source` and `source_document` records to DB. |

### Key Decisions

- **Source type (MVP):** YouTube only. One whitelisted channel to prove the pipeline.
- **Source granularity:** Channel-level. System discovers all videos automatically. (Ad-hoc single video URL support later.)
- **Incremental loading:** RSS feed polling + DB watermark (last video ID/publish date per channel) + checksum dedup.
- **Transcript method:** `youtube-transcript-api` (unofficial, no API quota cost). Fallback strategies (yt-dlp, Deepgram audio transcription) added later.
- **S3 format:** Structured JSON with timestamp segments. Plain text derived for downstream processing.
- **Sweep frequency:** Every 4-6 hours.
- **Error handling:** YouTube API rate limit → skip immediately and log. All other failures → Temporal retry with backoff, then skip and log.
- **Source management:** Seed from JSON file. Admin adds channels via API endpoint. Admin approval is manual judgment.
- **No** chunking, embeddings, text cleaning, diarization, or speaker attribution in MVP.

### S3 JSON Format

```json
{
  "video_id": "abc123",
  "channel_id": "UC...",
  "title": "SuperCoach Round 5 Preview",
  "published_at": "2026-03-09T10:00:00Z",
  "segments": [
    {"start": 0.0, "end": 4.5, "text": "Welcome back to SuperCoach TV", "speaker": null},
    {"start": 4.5, "end": 9.2, "text": "Today we're talking about...", "speaker": null}
  ]
}
```

## MVP Tasks

- [ ] Temporal workflow: `IntelSweepWorkflow` (runs every 4-6 hours)
- [ ] Discovery activity — poll RSS feeds for whitelisted channels, check watermark/checksum to find new videos
- [ ] Collection activity — fetch transcript via `youtube-transcript-api`, store JSON in S3 (`jeromelu-raw-transcripts` bucket)
- [ ] Processing activity — extract plain text from JSON segments
- [ ] Indexing activity — write `source` and `source_document` records to DB
- [ ] Source seed loader — load whitelisted channels from JSON file
- [ ] Admin API endpoint — `POST /admin/sources` to add new channels
- [ ] Error handling — skip+log for rate limits, Temporal retry for transient failures
- [ ] Deduplication — checksum-based duplicate detection (watermark + content hash)

## Future (Post-MVP)

- [ ] Ad-hoc single video URL ingestion (bypass channel subscription)
- [ ] Fallback transcript methods (yt-dlp, Deepgram audio transcription)
- [ ] Text normalisation and cleaning pipeline (filler words, caption overlap, misheard NRL names, ad removal)
- [ ] Chunking engine — custom chunking algorithm (TBD)
- [ ] Embedding generation — OpenAI embeddings API, store in pgvector
- [ ] Web article scraper (trafilatura or similar)
- [ ] Podcast ingestion — download audio, transcribe
- [ ] Radio show recording and transcription
- [ ] Source discovery — keyword-based search for unknown creators, surface to admin approval queue
- [ ] Adaptive sweep frequency (more frequent on Tues-Fri during NRL season)
