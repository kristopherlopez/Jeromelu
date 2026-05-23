---
tags: [area/architecture]
---

# Technology Stack

Current as of 2026-05-05. Reflects the post-Lightsail, audio-first reality
(see [09-aws-architecture](09-aws-architecture.md) and
[../sources/extraction-method.md](../sources/extraction-method.md)). For
the full status of each module, see
[../agents/system/README.md](../agents/system/README.md).

## Frontend
- **Next.js 16 + TypeScript**
- Tailwind CSS
- Server-rendered pages for SEO
- Dynamic modules for feed, wiki, ledger, ask-me

## Public / Admin API
- **FastAPI + Python**
- Pydantic for typed schemas
- SSE for streamed agentic events (Scout, Analyst); plain JSON otherwise
- Admin endpoints gated by `X-Admin-Key`

## Pipelines
Most production pipelines are CLI / cron-driven Python modules inside the `api`
container. The two surfaces:

- **Scout** (`services/api/app/scout/`) — agentic discovery via the Claude Agent SDK; deterministic enumeration / refresh; yt-dlp-based audio + low-res video acquisition.
- **Analyst** (`services/api/app/analyst/`) — Deepgram + pyannote transcription, voice / visual speaker identification, cross-modal fusion. Heavy inference can offload to the `services/gpu/` SageMaker Async endpoint when `LINEUP_REMOTE=1`.

**Workflow orchestration:** Temporal exists in `docker-compose.yml` for local
dev only (publishing, scraper, orchestrator workers). Not deployed to
Lightsail. New production pipelines run as cron jobs (`scripts/cron.d/jeromelu`)
or one-shot CLI invocations driven via `make` targets.

## Data Layer
- **PostgreSQL 16** with `pgvector` extension (`pgvector/pgvector:pg16` image, on the Lightsail box)
- pgvector for embeddings (text chunks, voiceprints, face embeddings)
- Postgres full-text search for lexical retrieval
- **Object storage** — S3 in `ap-southeast-2`:
  - `jeromelu-raw-audio` — full-episode m4a from yt-dlp
  - `jeromelu-raw-transcripts` — Deepgram + pyannote JSON, face-track JSON
  - `jeromelu-clean-documents` — cleaned transcripts (when cleaning pass exists)
  - `jeromelu-public-assets` — Postgres backups under `backups/postgres/`, public images
- Backups: nightly `pg_dump` to S3 with 14-day lifecycle expiry
- Migrations: hand-numbered SQL under `packages/db/migrations/`, applied via `make migrate`

## AI / ML Layer
- **LLM** — Anthropic (`claude-sonnet-4-6` for the Scout agentic loop today; broader use as more pipelines come online). Some legacy code still references OpenAI; migration in progress.
- **ASR** — Deepgram nova-3, batch prerecorded API, `language=en-AU`, keyterm vocabulary built from the canonical roster.
- **Diarisation** — `pyannote/speaker-diarization-3.1` (HuggingFace) — primary diarizer.
- **Voice embeddings** — `pyannote/wespeaker-voxceleb-resnet34-LM` (256-dim, bundled with the diarization pipeline).
- **Face detection / recognition** — InsightFace `buffalo_l` (RetinaFace + ArcFace, 512-dim).
- **Active speaker detection (ASD)** — mouth-opening heuristic from InsightFace `landmark_3d_68`. Real audio-sync ASD (Light-ASD / TalkNet / LoCoNet) is on the backlog.
- **Audio / video acquisition** — `yt-dlp` + `ffmpeg`.
- **Remote GPU** — SageMaker Async on `ml.g4dn.xlarge`, scale-to-zero. Container under `services/gpu/` bakes pyannote + InsightFace model weights at build time.

## Runtime / Infra
- **Single Lightsail VM** (`small_3_2`, Ubuntu 22.04) running Docker Compose: postgres, caddy, web, api.
- **CloudFront** in front of `jeromelu.ai` and `www`; `api.jeromelu.ai` direct to Lightsail.
- **Route 53** hosted zone; **ACM** in `us-east-1` for the CloudFront viewer cert.
- **GitHub Actions** for CI: build → push to ECR → self-hosted runner on the Lightsail box runs `scripts/lightsail-deploy.sh` (which also syncs `scripts/cron.d/jeromelu` into `/etc/cron.d/`). Full pipeline overview in [`docs/ops/ci-cd.md`](../ops/ci-cd.md).
- **Terraform** under `infra/terraform/` is the source of truth for AWS resources (S3, ECR, IAM, Route 53, CloudFront, Lightsail instance + IP + firewall).
- **Container registry** — ECR, two repos: `jeromelu/web`, `jeromelu/api`. Lifecycle keeps last 10 tagged + drops untagged after 14d.

## Observability
- Structured logs via Python `logging`; container logs to `journald` on Lightsail.
- `agent_runs` + `agent_events` Postgres tables for every Claude-Agent-SDK run (see [agent-audit.md](../agents/system/agent-audit.md)).
- S3 JSONL audit trail per run.
- No CloudWatch agent in V1; alarms deliberately deferred until there are real users.

## Service split (current)

| Service | Status | Location |
|---|---|---|
| `web` (Next.js) | Live | Lightsail container, image `jeromelu/web` |
| `api` (FastAPI — Scout + Analyst + admin) | Live | Lightsail container, image `jeromelu/api` |
| `postgres` | Live | Lightsail container, named volume |
| `caddy` | Live | Lightsail container, ACME via Let's Encrypt |
| `services/gpu/` (lineup remote inference) | Live (on-demand) | SageMaker Async, `ml.g4dn.xlarge`, scale-to-zero |
| `worker-publishing`, `worker-scraper`, `worker-orchestrator` | Dev-only (Temporal) | Local docker-compose, not deployed |
| `worker-ingestion` | Superseded | Replaced by Scout `audio.py` + Analyst `transcribe.py` |
| `worker-extraction`, `worker-decision` | Not built | — |

For per-module detail (driver, schedule, status), see
[../agents/system/README.md](../agents/system/README.md).

## Key Technical Principle
Keep the **public experience** and the **intelligence engine** separate, but
keep the **data layer unified**.
