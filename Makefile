.PHONY: up down db-shell api web logs clean prod-pull-raw prod-pull-raw-all prod-upload-clean prod-upload-claims prod-ingest prod-update-clean

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
