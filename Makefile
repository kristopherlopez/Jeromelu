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
