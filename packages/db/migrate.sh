#!/usr/bin/env bash
# Lightweight migration runner for Jeromelu.
# Tracks applied migrations in a `schema_migrations` table and applies
# any new .sql files from the migrations/ directory in numeric order.
#
# Usage:
#   ./migrate.sh                          # uses DATABASE_URL or defaults
#   ./migrate.sh --status                 # show applied vs pending
#   ./migrate.sh --baseline               # mark all existing migrations as applied
#   DATABASE_URL=postgres://... ./migrate.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATIONS_DIR="$SCRIPT_DIR/migrations"

# ---------------------------------------------------------------------------
# Connection — parse DATABASE_URL or fall back to defaults
# Accepts both postgresql:// and postgresql+psycopg:// (strips +driver)
# ---------------------------------------------------------------------------
RAW_URL="${DATABASE_URL:-postgresql://jeromelu_admin:localdev123@localhost:5440/jeromelu}"
# Strip SQLAlchemy driver suffix (e.g. +psycopg, +asyncpg)
CLEAN_URL="$(echo "$RAW_URL" | sed 's|postgresql+[a-z]*://|postgresql://|')"

PSQL="psql $CLEAN_URL -v ON_ERROR_STOP=1"

# ---------------------------------------------------------------------------
# Ensure tracking table exists
# ---------------------------------------------------------------------------
$PSQL -q <<'SQL'
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     VARCHAR(255) PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
SQL

# ---------------------------------------------------------------------------
# Collect applied versions
# ---------------------------------------------------------------------------
APPLIED=$($PSQL -Atq -c "SELECT version FROM schema_migrations ORDER BY version;")

# ---------------------------------------------------------------------------
# Helper: check if a version has been applied
# ---------------------------------------------------------------------------
is_applied() {
    echo "$APPLIED" | grep -qx "$1"
}

# ---------------------------------------------------------------------------
# --baseline: mark all migrations as applied without running them
# Use this on databases that already have all migrations applied via
# docker-entrypoint-initdb.d but no tracking table.
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--baseline" ]]; then
    echo "Baselining — marking all migrations as already applied:"
    for f in "$MIGRATIONS_DIR"/*.sql; do
        name="$(basename "$f")"
        if is_applied "$name"; then
            echo "  ·  $name  (already tracked)"
        else
            $PSQL -q -c "INSERT INTO schema_migrations (version) VALUES ('$name');"
            echo "  ✓  $name  (recorded)"
        fi
    done
    echo "Baseline complete."
    exit 0
fi

# ---------------------------------------------------------------------------
# --status: show migration state and exit
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--status" ]]; then
    echo "Migration status:"
    echo "─────────────────────────────────────────"
    for f in "$MIGRATIONS_DIR"/*.sql; do
        name="$(basename "$f")"
        if is_applied "$name"; then
            echo "  ✓  $name"
        else
            echo "  ·  $name  (pending)"
        fi
    done
    echo ""
    exit 0
fi

# ---------------------------------------------------------------------------
# Apply pending migrations
# ---------------------------------------------------------------------------
PENDING=0
for f in "$MIGRATIONS_DIR"/*.sql; do
    name="$(basename "$f")"

    if is_applied "$name"; then
        continue
    fi

    echo "Applying $name ..."
    $PSQL -q -f "$f"
    $PSQL -q -c "INSERT INTO schema_migrations (version) VALUES ('$name');"
    echo "  ✓ $name applied"
    PENDING=$((PENDING + 1))
done

if [[ $PENDING -eq 0 ]]; then
    echo "Database is up to date."
else
    echo "Applied $PENDING migration(s)."
fi
