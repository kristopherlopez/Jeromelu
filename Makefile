.PHONY: up down db-shell migrate migrate-status seed-teams seed-venues seed-players api web logs clean prod-pull-raw prod-pull-raw-all prod-upload-clean prod-upload-claims prod-ingest prod-update-clean prod-sync prod-sync-dry-run prod-sync-all prod-refresh-videos prod-seed-teams prod-seed-players prod-refresh-players deploy-prod prod-shell prod-logs

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

# Seed entities + player_attributes locally from a SC roster JSON dump.
# Reads scripts/data/scraped_players_api_raw.json (or the file passed as
# the first arg). Requires teams to be seeded first.
# Usage: make seed-players
seed-players:
	python scripts/data/seed_players_prod.py

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
