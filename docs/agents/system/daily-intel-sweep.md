---
tags: [area/agents, subarea/system, status/live]
---

# Daily Intel Sweep

The daily intel sweep discovers new YouTube videos from tracked channels, fetches their transcripts, and indexes them into the database. Downstream, transcripts are cleaned, claims are extracted, and results are pushed to production via S3 and the admin API.

```
YouTube Channels
    |
    v
[Temporal: 10 PM AEST daily]
    |
    v
1. Discovery ──> 2. Collection ──> 3. Indexing              AUTOMATED
   (RSS/yt-dlp)    (youtube-api)     (Source + Doc)          (Temporal)
    |
    v
S3 raw transcripts + PostgreSQL (sources, source_documents)
    |
    v
4. Pull from S3 ──> 5. Clean ──> 6. Extract Claims          LOCAL
   (aws s3 cp)    (/clean-transcript) (/process-transcript)  (Claude Code)
    |
    v
7. Upload to S3 (clean transcript + claims)
    |
    v
8. Ingest ──> 9. Update Clean Text (optional)               PRODUCTION
   (POST /api/admin/ingest)  (POST /api/admin/update-clean-text)  (API)
```

---

## Automated Pipeline (Temporal)

### Trigger

- **Schedule**: `daily-intel-sweep`, every day at 10:00 PM AEST
- **Jitter**: +/- 5 minutes
- **Task queue**: `ingestion`
- **Manual trigger**: `python -m app.trigger_sweep` from `services/worker-ingestion/`

### Activity 1: Discovery

Polls all active YouTube channels for new videos.

- Loads channels from DB (`platform='youtube'`, `active=true`)
- Tries RSS feed first (`youtube.com/feeds/videos.xml?channel_id={id}`), falls back to `yt-dlp`
- Filters to videos published after 2026-01-01
- Deduplicates against existing `sources.canonical_url`
- Updates `channels.last_polled_at`

**Output**: list of new `{video_id, title, published_at, channel_id, url}`

### Activity 2: Collection

Fetches auto-generated transcripts for each new video.

- Uses `youtube-transcript-api` to get segments `[{start, end, text}, ...]`
- Checks S3 cache at `youtube/{channel_id}/{video_id}.json` — skips if exists
- Uploads structured JSON to S3
- Computes SHA-256 checksum

**Retry**: 3 attempts, 5s initial delay, 2x backoff. Rate limits and missing transcripts are non-retryable.

### Activity 3: Indexing

Creates database records for collected transcripts.

- Creates `Source` (type `youtube`, `approved_flag=true`, `ingestion_status='completed'`)
- Creates `SourceDocument` (stores S3 key, raw plain text, checksum)
- Deduplicates via checksum — skips if already indexed
- Links source to its channel

**Output per sweep**:
```json
{
  "discovered": 10,
  "collected": 9,
  "indexed": 9,
  "errors": [{"video_id": "xyz", "stage": "collection", "error": "..."}]
}
```

---

## Local Pipeline (Claude Code Skills)

After the automated pipeline indexes raw transcripts, these steps run locally via Claude Code skills. Each step operates on transcript JSON files in `data/transcripts/`.

### Step 4: Pull Raw Transcripts from S3

Download raw transcripts from S3 to the local working directory so they can be cleaned and processed.

```bash
# Single transcript
make prod-pull-raw CHANNEL=UCxxx VIDEO=abc123

# All new transcripts from a channel
make prod-pull-raw-all CHANNEL=UCxxx
```

Files land at `data/transcripts/raw/{channel_id}_{video_id}.json`.

### Step 5: Clean Transcript

**Skill**: `/clean-transcript <raw-transcript-path>`

Fixes auto-caption artifacts — mangled player names, garbled words, broken phrases — using the player registry (`data/players.yaml`) and NRL domain knowledge.

- **Input**: `data/transcripts/raw/{channel_id}_{video_id}.json`
- **Output**: `data/transcripts/clean/{channel_id}_{video_id}.json`
- Preserves JSON structure, only modifies segment `text` fields

### Step 6: Extract Claims

**Skill**: `/process-transcript <clean-transcript-path>`

Multi-pass LLM extraction of NRL Supercoach claims (buy, sell, hold, captain, avoid, breakout, matchup edge) from the cleaned transcript.

- **Input**: clean transcript JSON
- **Output**: `data/transcripts/processed/{filename}.json` — array of claim objects with `claim_type`, `claim_text`, `player_name`, `polarity`, `strength`, `effective_round`, `season`

### Step 7: Persist

After extracting claims, there are two paths depending on the target environment:

**Local (test against local DB):**

**Skill**: `/upload-transcript <clean-transcript-path>`

Persists the transcript and extracted claims to the local database. Locates the matching claims file in `data/transcripts/processed/`, stitches and chunks the transcript, and writes Source, SourceDocument, SourceChunks, Entities, Claims, and ClaimChunks.

**Production (push to prod):**

Upload the clean transcript and claims to S3, then call the admin API to ingest (see Steps 8-9 below).

```bash
make prod-upload-clean  CHANNEL=UCxxx VIDEO=abc123
make prod-upload-claims CHANNEL=UCxxx VIDEO=abc123
```

Files land at:

```
s3://jeromelu-clean-documents/youtube/{channel_id}/{video_id}.json    # clean transcript
s3://jeromelu-clean-documents/claims/{video_id}.json                  # extracted claims
```

---

## Production Ingestion (API)

The production API reads transcripts and claims from S3 and writes to the database. No DB tunnel or direct database access needed.

### Step 8: Ingest

**Endpoint**: `POST /api/admin/ingest`

Pulls raw transcript, clean transcript, and claims from S3. Writes Source, SourceDocument, SourceChunks, Entities, Claims, and ClaimChunks to the database in a single transaction.

```bash
make prod-ingest CHANNEL=UCxxx VIDEO=abc123 ADMIN_KEY=xxx
```

```json
{
  "source_id": "uuid",
  "document_id": "uuid",
  "chunks_created": 142,
  "claims_created": 8
}
```

### Step 9: Update Clean Text (optional)

**Endpoint**: `POST /api/admin/update-clean-text`

Backfills `clean_text` on existing chunks when a clean transcript becomes available after the source was already ingested.

```bash
make prod-update-clean CHANNEL=UCxxx VIDEO=abc123 ADMIN_KEY=xxx
```

```json
{"source_id": "uuid", "chunks_updated": 142}
```

### Local Equivalents

For local development, the same operations run directly against the local database:

| Step | Production | Local |
|------|------------|-------|
| Persist | `prod-upload-clean` + `prod-upload-claims` + `prod-ingest` | `/upload-transcript <clean-transcript-path>` |
| Update clean text | `prod-upload-clean` + `prod-update-clean` | `python scripts/transcripts/process_transcript.py update-transcript <path>` |

### API Reference

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/admin/ingest` | POST | `X-Admin-Key` header | Full ingestion from S3 (transcript + claims -> DB) |
| `/api/admin/update-clean-text` | POST | `X-Admin-Key` header | Backfill `clean_text` on existing chunks from S3 |

Both require the admin API key from Parameter Store (`/jeromelu/admin-key`, SecureString).

### End-to-End Example

```bash
# 1. Pull raw transcript from S3
make prod-pull-raw CHANNEL=UCxxx VIDEO=abc123

# 2. Clean the transcript (Claude Code)
/clean-transcript data/transcripts/raw/UCxxx_abc123.json

# 3. Extract claims (Claude Code)
/process-transcript data/transcripts/clean/UCxxx_abc123.json

# 4a. LOCAL — persist to local DB
/upload-transcript data/transcripts/clean/UCxxx_abc123.json

# 4b. PRODUCTION — push to S3 then ingest via API
make prod-upload-clean  CHANNEL=UCxxx VIDEO=abc123
make prod-upload-claims CHANNEL=UCxxx VIDEO=abc123
make prod-ingest CHANNEL=UCxxx VIDEO=abc123 ADMIN_KEY=xxx
```

---

## Deduplication

Three layers prevent duplicate work:

| Layer | Check | Where |
|-------|-------|-------|
| Discovery | `sources.canonical_url` | New videos only |
| Collection | S3 key existence | Skip re-download |
| Indexing | `source_documents.checksum` | Skip re-index |

---

## File Structure

```
services/worker-ingestion/app/
├── workflows/intel_sweep.py      # Temporal workflow definition
├── activities/
│   ├── discovery.py              # Poll channels for new videos
│   ├── collection.py             # Fetch transcripts, upload S3
│   └── indexing.py               # Write Source + SourceDocument to DB
├── create_schedule.py            # Set up Temporal schedule
├── trigger_sweep.py              # Manual trigger
├── main.py                       # Worker entry point
└── seed_channels.py              # Bootstrap channels table

services/api/app/
└── routers/
    ├── sources.py                # GET /sources, /sources/{id}
    └── admin.py                  # POST /admin/ingest, /admin/update-clean-text

scripts/
├── process_transcript.py         # prepare / write / update-transcript / reset
└── extraction/
    ├── stitcher.py               # Dedup + join overlapping segments
    ├── chunker.py                # Map segments to chunks (1:1)
    ├── writer.py                 # Persist to DB with claim linking
    └── resolver.py               # Entity resolution (players, teams)

data/transcripts/                 # Local working files
├── raw/                          # Auto-caption JSON (from S3 or direct fetch)
├── clean/                        # Corrected JSON (player names fixed)
└── processed/                    # Extracted claims JSON

S3 buckets                        # Production storage
├── jeromelu-raw-transcripts/     # Raw transcripts (from automated sweep)
└── jeromelu-clean-documents/     # Clean transcripts + claims (from local upload)
```
