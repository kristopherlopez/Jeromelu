#!/usr/bin/env bash
# Wrapper for scripts/disk_report.py — weekly cron, Mondays 22:30 UTC.

set -uo pipefail

ENV_FILE="/opt/jeromelu/.env"
PYTHON_BIN="/usr/bin/python3"
SCRIPT="/opt/jeromelu/scripts/disk_report.py"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "$(date -u +%FT%TZ) disk-report: missing $ENV_FILE" >&2
  exit 2
fi
if ! "$PYTHON_BIN" -c 'import boto3' 2>/dev/null; then
  echo "$(date -u +%FT%TZ) disk-report: python3-boto3 not installed" >&2
  exit 2
fi

# shellcheck disable=SC1090
. "$ENV_FILE"

exec "$PYTHON_BIN" "$SCRIPT"
