# Local Development Connections

Infrastructure (Postgres, MinIO, Temporal) runs via Docker Compose. The API and web services run separately.

```bash
# 1. Start infrastructure
make up  # or: docker compose -f docker/docker-compose.yml up -d

# 2. Start API (separate terminal)
make api  # or: cd services/api && source .venv/Scripts/activate && uvicorn app.main:app --reload --port 8000

# 3. Start web (separate terminal)
make web  # or: cd services/web && npm run dev
```

---

## PostgreSQL (pgvector)

| Field | Value |
|-------|-------|
| Host | `localhost` |
| Port | `5440` |
| Database | `jeromelu` |
| User | `jeromelu_admin` |
| Password | `localdev123` |
| Connection string | `postgresql://jeromelu_admin:localdev123@localhost:5440/jeromelu` |

**Note:** Port 5440 is used to avoid conflict with a local Postgres installation on 5432.

**CLI:** `psql -h localhost -p 5440 -U jeromelu_admin -d jeromelu`

### Useful queries

```sql
-- All ingested videos
SELECT title, creator_name, published_at, ingestion_status
FROM sources ORDER BY published_at DESC;

-- Transcript lengths
SELECT s.title, length(d.raw_text) as chars, d.checksum
FROM sources s JOIN source_documents d ON s.source_id = d.source_id
ORDER BY length(d.raw_text) DESC;

-- Preview a transcript
SELECT left(d.raw_text, 500)
FROM source_documents d
JOIN sources s ON s.source_id = d.source_id
WHERE s.title LIKE '%FINAL TEAM%';

-- Count records per table
SELECT 'sources' as tbl, count(*) FROM sources
UNION ALL SELECT 'source_documents', count(*) FROM source_documents
UNION ALL SELECT 'entities', count(*) FROM entities
UNION ALL SELECT 'quotes', count(*) FROM quotes
UNION ALL SELECT 'claims', count(*) FROM claims;
```

---

## MinIO (S3-compatible)

| Field | Value |
|-------|-------|
| API endpoint | `http://localhost:9000` |
| Console URL | `http://localhost:9001` |
| Access key | `minioadmin` |
| Secret key | `minioadmin` |

### Buckets

| Bucket | Contents |
|--------|----------|
| `jeromelu-raw-transcripts` | Structured JSON transcripts (per-segment with timestamps) |
| `jeromelu-clean-documents` | Cleaned/processed documents (future) |
| `jeromelu-public-assets` | Public-facing assets (future) |

**S3 key format:** `youtube/{channel_id}/{video_id}.json`

---

## Temporal

| Field | Value |
|-------|-------|
| Server | `localhost:7233` |
| UI | `http://localhost:8080` |
| Namespace | `jeromelu` |

### Task queues

| Queue | Service |
|-------|---------|
| `orchestrator` | worker-orchestrator |
| `ingestion` | worker-ingestion |
| `extraction` | worker-extraction |
| `decision` | worker-decision |
| `publishing` | worker-publishing |

**Timezone:** All schedules use `Australia/Sydney`. The server runs in UTC but each schedule specifies its own timezone.

**CLI (inside container):** `docker exec jeromelu-temporal bash -c "tctl --address 172.22.0.4:7233 --namespace jeromelu workflow list"`

### Schedules

| Schedule | Frequency | Time | Script |
|----------|-----------|------|--------|
| `daily-intel-sweep` | Daily | 10:00 PM AEST/AEDT | `python -m app.create_schedule` |

---

## Running the ingestion worker locally

```bash
cd services/worker-ingestion

# Start the Temporal worker (listens for workflow tasks)
python -m app.main

# In another terminal — trigger a sweep manually
python -m app.trigger_sweep
```
