.PHONY: up down db-shell migrate migrate-status api web logs clean prod-pull-raw prod-pull-raw-all prod-upload-clean prod-upload-claims prod-ingest prod-update-clean prod-sync prod-sync-dry-run prod-sync-all

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
