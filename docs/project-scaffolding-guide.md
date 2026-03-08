# Jeromelu — Project Scaffolding & Local Development Guide

**Purpose:** Set up the monorepo structure, local development environment, and database schema so you can build and test services locally before deploying to AWS.

**Prerequisites:**
- Node.js 20+ and npm/pnpm
- Python 3.12+
- Docker and Docker Compose
- Git

---

## Phase 1 — Monorepo Structure

### Step 1.1 — Create Directory Structure

From the project root (`Jeromelu/`), create the following structure:

```
Jeromelu/
├── docs/                          # (already exists)
├── services/
│   ├── web/                       # Next.js frontend
│   ├── api/                       # FastAPI backend
│   ├── worker-ingestion/          # Source discovery and ingestion
│   ├── worker-extraction/         # Entity, quote, claim extraction
│   ├── worker-decision/           # Consensus, planning, decisioning
│   └── worker-publishing/         # Feed events, voice rendering
├── packages/
│   └── db/                        # Shared database migrations and schema
├── docker/
│   ├── docker-compose.yml         # Local development stack
│   ├── docker-compose.prod.yml    # Production-like local testing
│   └── .env.example               # Environment variable template
├── .gitignore
├── README.md
└── Makefile                       # Common commands
```

### Step 1.2 — Create .gitignore

Add a root `.gitignore` covering all services:

```
# Dependencies
node_modules/
__pycache__/
*.pyc
.venv/
venv/

# Environment
.env
.env.local
.env.production

# Build outputs
.next/
dist/
build/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Docker
docker/data/

# Sensitive files
docs/aws-resource-inventory.md
```

---

## Phase 2 — Database Setup

### Step 2.1 — Docker Compose for Local Development

Create `docker/docker-compose.yml`:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: jeromelu-postgres
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: jeromelu
      POSTGRES_USER: jeromelu_admin
      POSTGRES_PASSWORD: localdev123
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ../packages/db/migrations:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U jeromelu_admin -d jeromelu"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio
    container_name: jeromelu-minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  minio_data:
```

Notes:
- Uses `pgvector/pgvector:pg16` image which includes the pgvector extension pre-installed
- MinIO provides S3-compatible local object storage for transcripts and artefacts
- Data persists across restarts via named volumes

### Step 2.2 — Environment Variable Template

Create `docker/.env.example`:

```
# Database
DATABASE_URL=postgresql://jeromelu_admin:localdev123@localhost:5432/jeromelu

# S3 / MinIO (local)
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_RAW_BUCKET=jeromelu-raw-transcripts
S3_CLEAN_BUCKET=jeromelu-clean-documents
S3_ASSETS_BUCKET=jeromelu-public-assets

# OpenAI
OPENAI_API_KEY=sk-your-key-here

# App
ENV=development
SESSION_SECRET=local-dev-session-secret
ADMIN_API_KEY=local-dev-admin-key
```

### Step 2.3 — Database Migration: Initial Schema

Create `packages/db/migrations/001_initial_schema.sql`:

```sql
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- sources
CREATE TABLE sources (
    source_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type VARCHAR(20) NOT NULL CHECK (source_type IN ('youtube', 'podcast', 'web', 'radio', 'manual')),
    title TEXT NOT NULL,
    creator_name TEXT,
    canonical_url TEXT UNIQUE,
    approved_flag BOOLEAN NOT NULL DEFAULT FALSE,
    ingestion_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    published_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- source_documents
CREATE TABLE source_documents (
    document_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL REFERENCES sources(source_id),
    raw_text TEXT,
    cleaned_text TEXT,
    transcript_available BOOLEAN NOT NULL DEFAULT FALSE,
    language VARCHAR(10) DEFAULT 'en',
    checksum VARCHAR(64),
    chunk_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- source_chunks
CREATE TABLE source_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES source_documents(document_id),
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    start_offset INTEGER,
    end_offset INTEGER,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- entities
CREATE TABLE entities (
    entity_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('player', 'team', 'expert', 'matchup')),
    canonical_name TEXT NOT NULL,
    aliases TEXT[] DEFAULT '{}',
    metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- quotes
CREATE TABLE quotes (
    quote_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES source_documents(document_id),
    chunk_id UUID REFERENCES source_chunks(chunk_id),
    speaker_entity_id UUID REFERENCES entities(entity_id),
    quoted_text TEXT NOT NULL,
    start_offset INTEGER,
    end_offset INTEGER,
    said_at_reference TEXT,
    confidence REAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- claims
CREATE TABLE claims (
    claim_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quote_id UUID REFERENCES quotes(quote_id),
    subject_entity_id UUID REFERENCES entities(entity_id),
    claim_type VARCHAR(20) NOT NULL CHECK (claim_type IN ('buy', 'sell', 'hold', 'captain', 'avoid', 'breakout', 'matchup_edge')),
    polarity REAL,
    strength REAL,
    effective_round INTEGER,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- predictions
CREATE TABLE predictions (
    prediction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    predictor_entity_id UUID REFERENCES entities(entity_id),
    subject_entity_id UUID REFERENCES entities(entity_id),
    prediction_type VARCHAR(50),
    predicted_value_text TEXT,
    event_window TEXT,
    evidence_claim_ids UUID[] DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolution_status VARCHAR(20)
);

-- consensus_snapshots
CREATE TABLE consensus_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_entity_id UUID NOT NULL REFERENCES entities(entity_id),
    time_bucket TIMESTAMPTZ NOT NULL,
    buy_count INTEGER DEFAULT 0,
    sell_count INTEGER DEFAULT 0,
    hold_count INTEGER DEFAULT 0,
    neutral_count INTEGER DEFAULT 0,
    contrarian_score REAL,
    consensus_score REAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- decisions
CREATE TABLE decisions (
    decision_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    decision_type VARCHAR(30) NOT NULL CHECK (decision_type IN ('trade', 'captain', 'start_sit', 'squad_structure', 'article_topic', 'reply')),
    subject_entity_id UUID REFERENCES entities(entity_id),
    action_json JSONB NOT NULL DEFAULT '{}',
    rationale_summary TEXT,
    strategy_tag VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    executed_at TIMESTAMPTZ,
    public_flag BOOLEAN NOT NULL DEFAULT FALSE
);

-- plans
CREATE TABLE plans (
    plan_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    round_number INTEGER,
    plan_summary TEXT,
    scenario_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- events
CREATE TABLE events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(50) NOT NULL,
    related_entity_ids UUID[] DEFAULT '{}',
    related_decision_id UUID REFERENCES decisions(decision_id),
    related_prediction_id UUID REFERENCES predictions(prediction_id),
    display_text TEXT NOT NULL,
    display_mode VARCHAR(20) NOT NULL CHECK (display_mode IN ('thought', 'action', 'system', 'prediction', 'review')),
    visibility VARCHAR(10) NOT NULL DEFAULT 'public' CHECK (visibility IN ('public', 'private')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    immutable_hash VARCHAR(64)
);

-- outcomes
CREATE TABLE outcomes (
    outcome_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prediction_id UUID REFERENCES predictions(prediction_id),
    decision_id UUID REFERENCES decisions(decision_id),
    actual_value_json JSONB,
    result_label VARCHAR(20),
    scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_sources_type ON sources(source_type);
CREATE INDEX idx_sources_approved ON sources(approved_flag);
CREATE INDEX idx_source_documents_source ON source_documents(source_id);
CREATE INDEX idx_source_chunks_document ON source_chunks(document_id);
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_name ON entities(canonical_name);
CREATE INDEX idx_quotes_document ON quotes(document_id);
CREATE INDEX idx_quotes_speaker ON quotes(speaker_entity_id);
CREATE INDEX idx_claims_subject ON claims(subject_entity_id);
CREATE INDEX idx_claims_type ON claims(claim_type);
CREATE INDEX idx_predictions_predictor ON predictions(predictor_entity_id);
CREATE INDEX idx_predictions_subject ON predictions(subject_entity_id);
CREATE INDEX idx_consensus_subject_time ON consensus_snapshots(subject_entity_id, time_bucket);
CREATE INDEX idx_decisions_type ON decisions(decision_type);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_created ON events(created_at);
CREATE INDEX idx_events_visibility ON events(visibility);
```

---

## Phase 3 — Service Scaffolding

### Step 3.1 — API Service (FastAPI)

Create `services/api/requirements.txt`:

```
fastapi==0.115.*
uvicorn[standard]==0.34.*
sqlalchemy==2.0.*
psycopg[binary]==3.2.*
pydantic==2.10.*
pydantic-settings==2.7.*
boto3==1.36.*
openai==1.65.*
python-dotenv==1.0.*
```

Create `services/api/app/__init__.py` (empty file)

Create `services/api/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Jeromelu API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "jeromelu-api"}
```

Create `services/api/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 3.2 — Web Service (Next.js)

From `services/web/`, initialise the Next.js project:

```bash
cd services/web
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --no-import-alias
```

When prompted:
- **Would you like to use TypeScript?** Yes
- **Would you like to use ESLint?** Yes
- **Would you like to use Tailwind CSS?** Yes
- **Would you like your code inside a `src/` directory?** Yes
- **Would you like to use App Router?** Yes
- **Would you like to use Turbopack?** Yes

After creation, add a health endpoint. Create `services/web/src/app/api/health/route.ts`:

```typescript
import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({ status: "ok", service: "jeromelu-web" });
}
```

Create `services/web/Dockerfile`:

```dockerfile
FROM node:20-slim AS base

FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000

CMD ["node", "server.js"]
```

Add to `services/web/next.config.ts` (ensure standalone output):

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
```

### Step 3.3 — Worker Services (Python)

Each worker follows the same structure. Create for each of the 4 workers (`worker-ingestion`, `worker-extraction`, `worker-decision`, `worker-publishing`):

**Template — repeat for each worker:**

Create `services/{worker-name}/requirements.txt`:

```
sqlalchemy==2.0.*
psycopg[binary]==3.2.*
boto3==1.36.*
openai==1.65.*
python-dotenv==1.0.*
temporalio==1.9.*
```

Create `services/{worker-name}/app/__init__.py` (empty file)

Create `services/{worker-name}/app/main.py`:

```python
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting {worker-name}...")
    # Temporal worker registration will go here
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
```

Replace `{worker-name}` with the actual service name in the log message.

Create `services/{worker-name}/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "app.main"]
```

---

## Phase 4 — Local Development Workflow

### Step 4.1 — Start Local Infrastructure

```bash
cd docker
cp .env.example .env
docker compose up -d
```

This starts:
- PostgreSQL on `localhost:5432` (with pgvector and schema auto-applied)
- MinIO on `localhost:9000` (console at `localhost:9001`)

### Step 4.2 — Create MinIO Buckets

Open MinIO console at `http://localhost:9001` (login: `minioadmin` / `minioadmin`) and create:
- `jeromelu-raw-transcripts`
- `jeromelu-clean-documents`
- `jeromelu-public-assets`

Or via CLI:

```bash
docker exec jeromelu-minio mc alias set local http://localhost:9000 minioadmin minioadmin
docker exec jeromelu-minio mc mb local/jeromelu-raw-transcripts
docker exec jeromelu-minio mc mb local/jeromelu-clean-documents
docker exec jeromelu-minio mc mb local/jeromelu-public-assets
```

### Step 4.3 — Run API Locally

```bash
cd services/api
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../../docker/.env .env

uvicorn app.main:app --reload --port 8000
```

Verify: `http://localhost:8000/health` should return `{"status": "ok", "service": "jeromelu-api"}`

### Step 4.4 — Run Web Locally

```bash
cd services/web
npm install

npm run dev
```

Verify: `http://localhost:3000` should show the Next.js default page

### Step 4.5 — Verify Database Schema

Connect to local Postgres and confirm all tables exist:

```bash
docker exec -it jeromelu-postgres psql -U jeromelu_admin -d jeromelu -c "\dt"
```

Expected output: 11 tables (sources, source_documents, source_chunks, entities, quotes, claims, predictions, consensus_snapshots, decisions, plans, events, outcomes)

### Step 4.6 — Verify pgvector

```bash
docker exec -it jeromelu-postgres psql -U jeromelu_admin -d jeromelu -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

Expected output: `vector`

---

## Phase 5 — Makefile for Common Commands

Create `Makefile` in the project root:

```makefile
.PHONY: up down db-shell api web logs clean

# Start local infrastructure
up:
	cd docker && docker compose up -d

# Stop local infrastructure
down:
	cd docker && docker compose down

# Open database shell
db-shell:
	docker exec -it jeromelu-postgres psql -U jeromelu_admin -d jeromelu

# Run API locally
api:
	cd services/api && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Run web locally
web:
	cd services/web && npm run dev

# View logs
logs:
	cd docker && docker compose logs -f

# Clean everything (removes data volumes)
clean:
	cd docker && docker compose down -v
```

---

## Phase 6 — Build Docker Images Locally

Test that all Dockerfiles build before pushing to ECR.

```bash
# API
docker build -t jeromelu/api:local services/api/

# Web
docker build -t jeromelu/web:local services/web/

# Workers
docker build -t jeromelu/worker-ingestion:local services/worker-ingestion/
docker build -t jeromelu/worker-extraction:local services/worker-extraction/
docker build -t jeromelu/worker-decision:local services/worker-decision/
docker build -t jeromelu/worker-publishing:local services/worker-publishing/
```

Test locally:

```bash
# API
docker run --rm -p 8000:8000 jeromelu/api:local
# Visit http://localhost:8000/health

# Web
docker run --rm -p 3000:3000 jeromelu/web:local
# Visit http://localhost:3000
```

---

## Verification Checklist

- [ ] `docker compose up -d` starts Postgres and MinIO without errors
- [ ] All 11 database tables created (verify with `\dt`)
- [ ] pgvector extension enabled
- [ ] MinIO has 3 buckets
- [ ] `http://localhost:8000/health` returns ok (API)
- [ ] `http://localhost:3000` loads (Web)
- [ ] All 6 Docker images build successfully
- [ ] Project committed to git

---

## What This Unlocks

With scaffolding complete, you can:

1. **Build Phase 1 features** (source ingestion, extraction pipeline)
2. **Push Docker images to ECR** and see ECS services come alive
3. **Set up CI/CD** (separate guide) to automate build/deploy
4. **Visit `https://jeromelu.ai`** and see a live response
