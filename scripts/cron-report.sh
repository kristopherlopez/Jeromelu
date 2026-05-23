#!/usr/bin/env bash
# Wrapper for scripts/cron_report.py — sources runtime env and invokes
# system python3. Scheduled by /etc/cron.d/jeromelu at 00:30 UTC daily.
#
# boto3 comes from the python3-boto3 apt package, installed by
# scripts/lightsail-deploy.sh on first deploy. No venv — one system
# package is simpler than venv + python3-venv, and ops digests don't
# need a pinned boto3 version.
#
# .env supplies POSTGRES_USER, POSTGRES_DB, and GITHUB_TOKEN.
# GITHUB_TOKEN is optional — without it the cost-report row degrades
# to status=unknown rather than failing the whole report.

set -uo pipefail

ENV_FILE="/opt/jeromelu/.env"
PYTHON_BIN="/usr/bin/python3"
SCRIPT="/opt/jeromelu/scripts/cron_report.py"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "$(date -u +%FT%TZ) cron-report: missing $ENV_FILE" >&2
  exit 2
fi
if ! "$PYTHON_BIN" -c 'import boto3' 2>/dev/null; then
  echo "$(date -u +%FT%TZ) cron-report: python3-boto3 not installed — has lightsail-deploy.sh run?" >&2
  exit 2
fi

# shellcheck disable=SC1090
. "$ENV_FILE"

exec "$PYTHON_BIN" "$SCRIPT"
