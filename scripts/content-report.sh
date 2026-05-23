#!/usr/bin/env bash
# Wrapper for scripts/content_report.py — weekly cron, Mondays 22:00 UTC.

set -uo pipefail

ENV_FILE="/opt/jeromelu/.env"
PYTHON_BIN="/usr/bin/python3"
SCRIPT="/opt/jeromelu/scripts/content_report.py"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "$(date -u +%FT%TZ) content-report: missing $ENV_FILE" >&2
  exit 2
fi
if ! "$PYTHON_BIN" -c 'import boto3' 2>/dev/null; then
  echo "$(date -u +%FT%TZ) content-report: python3-boto3 not installed" >&2
  exit 2
fi

# shellcheck disable=SC1090
. "$ENV_FILE"

exec "$PYTHON_BIN" "$SCRIPT"
