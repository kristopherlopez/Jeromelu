#!/usr/bin/env bash
# Wrapper for scripts/cron_report.py — sources runtime env and invokes
# the ops venv. Scheduled by /etc/cron.d/jeromelu at 00:30 UTC daily.
#
# The ops venv (/opt/jeromelu/.venv-ops) is bootstrapped by
# scripts/lightsail-deploy.sh — boto3 + nothing else. We keep this venv
# separate from any service venv so deploys of the api image can't
# accidentally pull dependencies out from under cron.
#
# .env supplies POSTGRES_USER, POSTGRES_DB, and GITHUB_TOKEN.
# GITHUB_TOKEN is optional — without it the cost-report row degrades
# to status=unknown rather than failing the whole report.

set -uo pipefail

ENV_FILE="/opt/jeromelu/.env"
VENV_PY="/opt/jeromelu/.venv-ops/bin/python"
SCRIPT="/opt/jeromelu/scripts/cron_report.py"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "$(date -u +%FT%TZ) cron-report: missing $ENV_FILE" >&2
  exit 2
fi
if [[ ! -x "$VENV_PY" ]]; then
  echo "$(date -u +%FT%TZ) cron-report: missing venv at $VENV_PY — has lightsail-deploy.sh run?" >&2
  exit 2
fi

# shellcheck disable=SC1090
. "$ENV_FILE"

exec "$VENV_PY" "$SCRIPT"
