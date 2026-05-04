.PHONY: up down db-shell migrate migrate-status seed-teams seed-venues fetch-players seed-players api web logs clean collect-audio collect-video transcribe extract-transcript diarize diarize-compare enroll-voice enroll-face lineup-build lineup-deploy lineup-status lineup-delete prod-pull-raw prod-pull-raw-all prod-upload-clean prod-upload-claims prod-ingest prod-update-clean prod-sync prod-sync-dry-run prod-sync-all prod-refresh-videos prod-refresh-channel-stats prod-channel-coverage prod-seed-teams prod-seed-players prod-refresh-players prod-fetch-and-refresh-players prod-refresh-players-nrlcom deploy-prod prod-shell prod-logs

# Start local infrastructure
up:
	cd docker && docker compose up -d

# Stop local infrastructure
down:
	cd docker && docker compose down

# Run pending database migrations
migrate:
	bash packages/db/migrate.sh

# Show migration status (applied vs pending)
migrate-status:
	bash packages/db/migrate.sh --status

# Seed the teams table from data/teams.yaml (NRL + reserve grades + NRLW).
# Idempotent — safe to re-run.
seed-teams:
	python scripts/data/seed_teams.py

# Seed the venues table from data/venues.yaml. Idempotent.
seed-venues:
	python scripts/data/seed_venues.py

# Fetch the SC player roster (unauthenticated GET) and regenerate the
# yaml registry consumed by the transcript-cleaning pipeline. Output:
# scripts/data/scraped_players_api_raw.json + data/players.yaml.
# Cron-safe — no browser, no OAuth, no interactive 2FA.
# Usage: make fetch-players [SEASON=2026]
SEASON ?= $(shell python -c "from datetime import date; print(date.today().year)")
fetch-players:
	python scripts/data/fetchers/fetch_supercoach_players.py --season $(SEASON)
	node scripts/data/generate_players_yaml.js

# Seed people + people_attributes locally from a SC roster JSON dump.
# Reads scripts/data/scraped_players_api_raw.json (or the file passed as
# the first arg). Requires teams to be seeded first. Run `make fetch-players`
# beforehand if the JSON is stale.
# Usage: make seed-players
seed-players:
	python scripts/data/seed_players_prod.py

# Scout — acquire audio for one source (yt-dlp → s3://jeromelu-raw-audio).
# Sets sources.audio_s3_key and ingestion_status='collected'. Idempotent on
# the S3 object — safe to re-run.
# Usage: make collect-audio SOURCE_ID=<uuid>
collect-audio:
	@test -n "$(SOURCE_ID)" || (echo "SOURCE_ID is required: make collect-audio SOURCE_ID=<uuid>" && exit 2)
	. services/api/.venv/Scripts/activate && S3_ENDPOINT='' PYTHONPATH=services/api python -m app.scout.audio_cli $(SOURCE_ID)

# Scout — acquire low-res video for one source (yt-dlp 360p by default →
# s3://jeromelu-raw-audio with .video.mp4 suffix). Used by Phase 4 visual
# identification. Independent of audio acquisition; idempotent.
# Usage: make collect-video SOURCE_ID=<uuid> [QUALITY=240|360|480|720]
collect-video:
	@test -n "$(SOURCE_ID)" || (echo "SOURCE_ID is required: make collect-video SOURCE_ID=<uuid>" && exit 2)
	. services/api/.venv/Scripts/activate && S3_ENDPOINT='' PYTHONPATH=services/api python -m app.scout.video_cli $(SOURCE_ID) $(if $(QUALITY),--quality $(QUALITY))

# Analyst — transcribe a collected source via Deepgram (diarisation + keyterm).
# Requires audio_s3_key to be set (run collect-audio first). Writes the
# Deepgram JSON to s3://jeromelu-raw-transcripts and source_documents +
# source_speakers + source_chunks rows. Sets transcription_status='transcribed'.
# Usage: make transcribe SOURCE_ID=<uuid> [FORCE=1]
transcribe:
	@test -n "$(SOURCE_ID)" || (echo "SOURCE_ID is required: make transcribe SOURCE_ID=<uuid>" && exit 2)
	. services/api/.venv/Scripts/activate && S3_ENDPOINT='' PYTHONPATH=services/api python -m app.analyst.transcribe_cli $(SOURCE_ID) $(if $(FORCE),--force)

# Convenience target: run Scout (collect-audio) then Analyst (transcribe) in
# sequence for a single source. The two steps stay independent — a Deepgram
# failure leaves the audio in S3 for retry without re-downloading.
# Usage: make extract-transcript SOURCE_ID=<uuid> [FORCE=1]
extract-transcript: collect-audio transcribe

# Phase 1 speaker-identification — run pyannote/speaker-diarization-3.1 on a
# Source's audio and persist the JSON to s3://jeromelu-raw-transcripts. NO DB
# writes; this is the side-by-side decision-gate experiment that informs
# whether we proceed to Phase 2 (replace Deepgram's diarizer). Requires
# HUGGINGFACE_TOKEN in .env and `pip install -r services/api/requirements.txt`.
# Usage: make diarize SOURCE_ID=<uuid> [FORCE=1]
diarize:
	@test -n "$(SOURCE_ID)" || (echo "SOURCE_ID is required: make diarize SOURCE_ID=<uuid>" && exit 2)
	. services/api/.venv/Scripts/activate && S3_ENDPOINT='' PYTHONPATH=services/api python -m app.analyst.diarize_cli $(SOURCE_ID) $(if $(FORCE),--force)

# Print a side-by-side comparison of Deepgram and pyannote diarization for
# a single source: speaker counts, confusion matrix, label alignment, and
# agreement %. Read-only. Use to evaluate the Phase 1 decision-gate.
# Usage: make diarize-compare SOURCE_ID=<uuid> [INTERVAL=2.0] [SHOW_ALL=1]
diarize-compare:
	@test -n "$(SOURCE_ID)" || (echo "SOURCE_ID is required: make diarize-compare SOURCE_ID=<uuid>" && exit 2)
	. services/api/.venv/Scripts/activate && S3_ENDPOINT='' PYTHONPATH=services/api python -m app.analyst.diarize_compare $(SOURCE_ID) $(if $(INTERVAL),--interval $(INTERVAL)) $(if $(SHOW_ALL),--show-all-rows)

# Phase 3 voice enrollment — extract sliding-window embeddings from a
# known span of source audio and write one PersonVoiceprint row per
# window. Used during bootstrap to seed the voice registry. Recommended:
# >=10s of clean monologue per enrollment, 2-3 non-contiguous spans per
# Person to capture acoustic variation.
# Usage: make enroll-voice PERSON_ID=<uuid> SOURCE_ID=<uuid> START_TS=<sec> END_TS=<sec>
enroll-voice:
	@test -n "$(PERSON_ID)" || (echo "PERSON_ID is required" && exit 2)
	@test -n "$(SOURCE_ID)" || (echo "SOURCE_ID is required" && exit 2)
	@test -n "$(START_TS)" || (echo "START_TS is required" && exit 2)
	@test -n "$(END_TS)" || (echo "END_TS is required" && exit 2)
	. services/api/.venv/Scripts/activate && S3_ENDPOINT='' PYTHONPATH=services/api python -m app.analyst.enroll_voice_cli $(PERSON_ID) $(SOURCE_ID) $(START_TS) $(END_TS)

# Phase 4 face enrollment — write a person_face_embeddings row from a
# still image or a frame extracted from a source's video. Two modes:
#   make enroll-face PERSON_ID=<uuid> IMAGE=path/to/headshot.jpg
#   make enroll-face PERSON_ID=<uuid> SOURCE_ID=<uuid> FRAME_TS=<sec>
enroll-face:
	@test -n "$(PERSON_ID)" || (echo "PERSON_ID is required" && exit 2)
	@if [ -n "$(IMAGE)" ]; then \
		. services/api/.venv/Scripts/activate && S3_ENDPOINT='' PYTHONPATH=services/api python -m app.analyst.enroll_face_cli $(PERSON_ID) --image "$(IMAGE)"; \
	elif [ -n "$(SOURCE_ID)" ] && [ -n "$(FRAME_TS)" ]; then \
		. services/api/.venv/Scripts/activate && S3_ENDPOINT='' PYTHONPATH=services/api python -m app.analyst.enroll_face_cli $(PERSON_ID) --source-id $(SOURCE_ID) --frame-ts $(FRAME_TS); \
	else \
		echo "Need IMAGE=path OR (SOURCE_ID=<uuid> FRAME_TS=<sec>)" && exit 2; \
	fi

# Phase 5.5 — Lineup on SageMaker Async. Build the GPU container and push
# to ECR. Reads HUGGINGFACE_API_KEY from .env and passes it as a Buildkit
# secret (so the token doesn't land in image layers). One-time AWS setup
# is in services/gpu/SETUP.md.
# Usage: make lineup-build [TAG=v2]
lineup-build:
	@test -n "$(HUGGINGFACE_API_KEY)" || (set -a; . .env; set +a; bash services/gpu/build_and_push.sh $(TAG)) || bash services/gpu/build_and_push.sh $(TAG)

# Deploy / update the SageMaker model + endpoint config + endpoint.
# Idempotent — first run creates, subsequent runs roll forward.
# Usage: make lineup-deploy [TAG=v2]
lineup-deploy:
	. services/api/.venv/Scripts/activate && export S3_ENDPOINT="" && PYTHONPATH=services/api:packages/shared python services/gpu/deploy.py $(TAG)

# Inspect the endpoint state.
lineup-status:
	. services/api/.venv/Scripts/activate && export S3_ENDPOINT="" && PYTHONPATH=services/api:packages/shared python -c "import boto3; from jeromelu_shared.config import settings; sm = boto3.client('sagemaker', region_name=settings.lineup_aws_region); info = sm.describe_endpoint(EndpointName=settings.lineup_endpoint_name); print('status:', info['EndpointStatus']); print('config:', info['EndpointConfigName']); print('updated:', info['LastModifiedTime'])"

# Tear down the endpoint when you're done iterating (no idle cost on
# Async, but explicit cleanup avoids surprise charges from leftover
# endpoint configs / models).
# Usage: make lineup-delete
lineup-delete:
	. services/api/.venv/Scripts/activate && PYTHONPATH=services/api:packages/shared python -c "import boto3; from jeromelu_shared.config import settings; sm = boto3.client('sagemaker', region_name=settings.lineup_aws_region); name = settings.lineup_endpoint_name; print(f'deleting endpoint {name}'); sm.delete_endpoint(EndpointName=name); print('done')"

# Open database shell
db-shell:
	docker exec -it jeromelu-postgres psql -U jeromelu_admin -d jeromelu

# Run API locally. S3_ENDPOINT="" flips to real AWS — matches the
# transcribe / scout / analyst CLIs so presigned URLs (Phase 4b video
# overlay, Phase 1+ Deepgram URL handoff) point at the actual buckets
# the data lives in.
#
# `export VAR=...; cmd` rather than the inline `VAR=... cmd` form because
# the latter doesn't propagate reliably to `uvicorn`'s reloader child
# processes under Git Bash + GNU Make on Windows.
api:
	. services/api/.venv/Scripts/activate && export S3_ENDPOINT="" && export PYTHONPATH=services/api && uvicorn app.main:app --reload --port 8000

# Run web locally
web:
	cd services/web && npm run dev

# View logs
logs:
	cd docker && docker compose logs -f

# Clean everything (removes data volumes)
clean:
	cd docker && docker compose down -v

# --- Production ---

PROD_API = https://api.jeromelu.ai
REGION = ap-southeast-2
RAW_BUCKET = jeromelu-raw-transcripts
CLEAN_BUCKET = jeromelu-clean-documents

# Pull a single raw transcript from S3 to local
# Usage: make prod-pull-raw CHANNEL=UCxxx VIDEO=abc123
prod-pull-raw:
	@mkdir -p data/transcripts/raw
	aws s3 cp s3://$(RAW_BUCKET)/youtube/$(CHANNEL)/$(VIDEO).json \
		data/transcripts/raw/$(CHANNEL)_$(VIDEO).json \
		--region $(REGION)

# Pull all raw transcripts for a channel from S3
# Usage: make prod-pull-raw-all CHANNEL=UCxxx
prod-pull-raw-all:
	@mkdir -p data/transcripts/raw
	aws s3 cp s3://$(RAW_BUCKET)/youtube/$(CHANNEL)/ \
		data/transcripts/raw/ \
		--recursive --region $(REGION)

# Upload clean transcript to S3
# Usage: make prod-upload-clean CHANNEL=UCxxx VIDEO=abc123
prod-upload-clean:
	aws s3 cp data/transcripts/clean/$(CHANNEL)_$(VIDEO).json \
		s3://$(CLEAN_BUCKET)/youtube/$(CHANNEL)/$(VIDEO).json \
		--region $(REGION)

# Upload claims to S3
# Usage: make prod-upload-claims VIDEO=abc123
prod-upload-claims:
	aws s3 cp data/transcripts/processed/$(CHANNEL)_$(VIDEO).json \
		s3://$(CLEAN_BUCKET)/claims/$(VIDEO).json \
		--region $(REGION)

# Ingest transcript + claims from S3 into prod DB
# Usage: make prod-ingest CHANNEL=UCxxx VIDEO=abc123 ADMIN_KEY=xxx
prod-ingest:
	curl -s -X POST $(PROD_API)/api/admin/ingest \
		-H "Content-Type: application/json" \
		-H "X-Admin-Key: $(ADMIN_KEY)" \
		-d '{"video_id":"$(VIDEO)","channel_id":"$(CHANNEL)"}' | python -m json.tool

# Backfill clean_text on existing chunks from S3
# Usage: make prod-update-clean CHANNEL=UCxxx VIDEO=abc123 ADMIN_KEY=xxx
prod-update-clean:
	curl -s -X POST $(PROD_API)/api/admin/update-clean-text \
		-H "Content-Type: application/json" \
		-H "X-Admin-Key: $(ADMIN_KEY)" \
		-d '{"video_id":"$(VIDEO)","channel_id":"$(CHANNEL)"}' | python -m json.tool

# Weekly Scout refresh — incrementally enumerate new videos on every active
# YouTube channel, then refresh view/like/comment counts on every YouTube
# source into video_metrics. Idempotent. Wire to cron on the Lightsail box.
# Usage: make prod-refresh-videos ADMIN_KEY=xxx
prod-refresh-videos:
	curl -s -X POST $(PROD_API)/api/admin/scout/refresh-videos \
		-H "X-Admin-Key: $(ADMIN_KEY)" | python -m json.tool

# Per-channel ad-hoc refresh — enumerate uploads + snapshot stats for one
# channel. Accepts a UUID or a slug (e.g. CHANNEL=bloke-in-a-bar). Defaults
# to incremental; pass FULL_BACKFILL=1 to ignore the cursor and re-pull up
# to 200 videos. Used to recover from a failed approval-time enumerate or
# to force-pull a single channel without waiting for the weekly cron.
# Usage: make prod-refresh-channel-videos CHANNEL=<uuid-or-slug> [FULL_BACKFILL=1] ADMIN_KEY=xxx
prod-refresh-channel-videos:
	curl -s -X POST "$(PROD_API)/api/admin/scout/channels/$(CHANNEL)/refresh-videos$(if $(FULL_BACKFILL),?full_backfill=true,)" \
		-H "X-Admin-Key: $(ADMIN_KEY)" | python -m json.tool

# Daily channel stats refresh — snapshot subscriber/video/view counts for
# every active YouTube channel into channel_metrics. ~1 quota unit per 50
# channels, safe to run daily. Wire to cron alongside prod-refresh-videos.
# Usage: make prod-refresh-channel-stats ADMIN_KEY=xxx
prod-refresh-channel-stats:
	curl -s -X POST $(PROD_API)/api/admin/scout/refresh-channel-stats \
		-H "X-Admin-Key: $(ADMIN_KEY)" | python -m json.tool

# Channel coverage audit — for each active YouTube channel, compare
# YouTube's reported video count (from channel_metrics) against how many
# `sources` rows we have. Pure DB read, no API quota cost.
# Usage: make prod-channel-coverage ADMIN_KEY=xxx [ONLY_GAPS=1]
prod-channel-coverage:
	curl -s -G $(PROD_API)/api/admin/scout/channel-coverage \
		$(if $(ONLY_GAPS),--data-urlencode "only_gaps=true",) \
		-H "X-Admin-Key: $(ADMIN_KEY)" | python -m json.tool

# First-run prod team seed — converts local data/teams.yaml to JSON in
# memory and POSTs it to /api/admin/teams/seed. Idempotent: re-running
# only bumps updated_at on the existing rows. Run this before
# prod-seed-players (player_attributes FKs to teams).
# Usage: make prod-seed-teams ADMIN_KEY=xxx [TEAMS_FILE=path/to/teams.yaml]
TEAMS_FILE ?= data/teams.yaml
prod-seed-teams:
	python -c "import json, sys, yaml; \
		sys.stdout.write(json.dumps(yaml.safe_load(open('$(TEAMS_FILE)', encoding='utf-8'))))" \
	| curl -s -X POST $(PROD_API)/api/admin/teams/seed \
		-H "Content-Type: application/json" \
		-H "X-Admin-Key: $(ADMIN_KEY)" \
		--data-binary @- | python -m json.tool

# First-run prod player seed — POSTs the SC roster JSON to the admin
# endpoint. Idempotent: existing player_attributes rows are left alone.
# Requires teams already seeded in prod (run `make prod-seed-teams` first).
# Usage: make prod-seed-players ADMIN_KEY=xxx [ROSTER_FILE=path/to/roster.json]
ROSTER_FILE ?= scripts/data/scraped_players_api_raw.json
prod-seed-players:
	curl -s -X POST $(PROD_API)/api/admin/players/seed \
		-H "Content-Type: application/json" \
		-H "X-Admin-Key: $(ADMIN_KEY)" \
		--data-binary @$(ROSTER_FILE) | python -m json.tool

# Weekly prod player refresh — POSTs a fresh SC roster, applies SCD-2
# transitions for team / position changes and adds rows for new players.
# Run after `/scrape-supercoach` produces a fresh roster file.
# Usage: make prod-refresh-players ADMIN_KEY=xxx [ROSTER_FILE=path/to/roster.json]
prod-refresh-players:
	curl -s -X POST $(PROD_API)/api/admin/players/refresh \
		-H "Content-Type: application/json" \
		-H "X-Admin-Key: $(ADMIN_KEY)" \
		--data-binary @$(ROSTER_FILE) | python -m json.tool

# Server-side weekly refresh — the API container fetches the SC roster
# itself (unauthenticated GET) and applies the SCD-2 diff in one call.
# Preferred over prod-refresh-players because it removes the "ship the
# JSON from a laptop" step. Cron-friendly. Wire to crontab on the
# Lightsail box for the weekly Tuesday refresh.
# Usage: make prod-fetch-and-refresh-players ADMIN_KEY=xxx [SEASON=2026]
prod-fetch-and-refresh-players:
	curl -s -X POST "$(PROD_API)/api/admin/players/fetch-and-refresh$(if $(SEASON),?season=$(SEASON))" \
		-H "X-Admin-Key: $(ADMIN_KEY)" | python -m json.tool

# nrl.com profile-page enrichment — walks every current player row,
# fetches their nrl.com profile, parses the JSON-LD, and promotes dob /
# image_url / birthplace_text / height_cm / weight_kg. Sequential, ~2-3
# min for a full run. Pass TEAM=Broncos for a single-club test, or
# RATE_LIMIT_MS=200 to slow down if you hit upstream throttling.
# Usage: make prod-refresh-players-nrlcom ADMIN_KEY=xxx [TEAM=Broncos] [RATE_LIMIT_MS=200]
prod-refresh-players-nrlcom:
	curl -sS --max-time 600 -X POST \
		"$(PROD_API)/api/admin/players/refresh-nrlcom?$(if $(TEAM),team=$(TEAM)&)$(if $(RATE_LIMIT_MS),rate_limit_ms=$(RATE_LIMIT_MS))" \
		-H "X-Admin-Key: $(ADMIN_KEY)" | python -m json.tool

# Sync raw transcripts from local MinIO to production S3
# Requires: Docker running (MinIO) + AWS credentials configured
prod-sync:
	python scripts/sync_minio_to_s3.py

# Dry run — show what would be synced without uploading
prod-sync-dry-run:
	python scripts/sync_minio_to_s3.py --dry-run

# Full sync: copy MinIO -> S3, then ingest all clean+claims transcripts
# Usage: make prod-sync-all ADMIN_KEY=xxx
prod-sync-all:
	python scripts/sync_minio_to_s3.py
	@echo "\nUploading clean transcripts and claims to S3..."
	@for f in data/transcripts/clean/*.json; do \
		filename=$$(basename "$$f" .json); \
		channel=$$(echo "$$filename" | sed 's/_[^_]*$$//'); \
		video=$$(echo "$$filename" | sed 's/^.*_//'); \
		echo "Uploading clean: $$channel/$$video"; \
		aws s3 cp "$$f" "s3://$(CLEAN_BUCKET)/youtube/$$channel/$$video.json" --region $(REGION); \
		if [ -f "data/transcripts/processed/$$filename.json" ]; then \
			echo "Uploading claims: $$video"; \
			aws s3 cp "data/transcripts/processed/$$filename.json" "s3://$(CLEAN_BUCKET)/claims/$$video.json" --region $(REGION); \
			echo "Ingesting: $$channel/$$video"; \
			curl -s -X POST $(PROD_API)/api/admin/ingest \
				-H "Content-Type: application/json" \
				-H "X-Admin-Key: $(ADMIN_KEY)" \
				-d "{\"video_id\":\"$$video\",\"channel_id\":\"$$channel\"}" | python -m json.tool; \
		fi; \
	done
	@echo "\nSync complete."

# --- Lightsail Production ---

LIGHTSAIL_HOST ?= jeromelu-prod

# Trigger a deploy of the latest master to Lightsail (pulls images and restarts).
# Usage: make deploy-prod IMAGE_TAG=<git-sha>   (omit IMAGE_TAG to use :latest)
deploy-prod:
	ssh $(LIGHTSAIL_HOST) 'IMAGE_TAG=$(IMAGE_TAG) /opt/jeromelu/scripts/lightsail-deploy.sh'

# Open a shell on the Lightsail box.
prod-shell:
	ssh $(LIGHTSAIL_HOST)

# Tail compose logs on the Lightsail box.
prod-logs:
	ssh $(LIGHTSAIL_HOST) 'cd /opt/jeromelu/docker && docker compose -f docker-compose.prod.yml logs -f --tail=200'
