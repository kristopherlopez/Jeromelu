#!/usr/bin/env bash
# Docker entrypoint init script — runs the migration runner against the local DB.
# Mounted at /docker-entrypoint-initdb.d/ so Postgres executes it on first start.
# On subsequent starts, `make migrate` applies any new migrations.

set -euo pipefail

MIGRATIONS_DIR="/migrations"

# Ensure tracking table exists
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     VARCHAR(255) PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
SQL

# Apply all migrations in order and record them
for f in "$MIGRATIONS_DIR"/*.sql; do
    name="$(basename "$f")"
    echo "Applying $name ..."
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "$f"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
        -c "INSERT INTO schema_migrations (version) VALUES ('$name') ON CONFLICT DO NOTHING;"
    echo "  ✓ $name"
done

echo "All migrations applied and tracked."
