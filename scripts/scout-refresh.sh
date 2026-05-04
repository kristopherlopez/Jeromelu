#!/usr/bin/env bash
# Wrapper around the prod admin /api/admin/scout/refresh-* endpoints.
# Used by cron (scripts/cron.d/jeromelu) to refresh channel and video
# metrics on a schedule.
#
# Usage: scout-refresh.sh {channel-stats|videos}
#
# Sources /opt/jeromelu/.env to pick up ADMIN_KEY. Logs response status +
# body to /var/log/jeromelu/scout-refresh.log so non-2xx (which curl does
# not surface as a non-zero exit on its own) is recoverable after the
# fact. Returns non-zero on non-2xx so cron / external monitoring can
# pick up failures.
#
# Tail /var/log/jeromelu/scout-refresh.log to see recent runs.

set -euo pipefail

JOB="${1:-}"
case "$JOB" in
  channel-stats) ENDPOINT="refresh-channel-stats" ;;
  videos)        ENDPOINT="refresh-videos" ;;
  *) echo "usage: $0 {channel-stats|videos}" >&2; exit 2 ;;
esac

# shellcheck disable=SC1091
. /opt/jeromelu/.env

API_URL="https://api.jeromelu.ai/api/admin/scout/${ENDPOINT}"
LOG_DIR="/var/log/jeromelu"
LOG_FILE="${LOG_DIR}/scout-refresh.log"

mkdir -p "$LOG_DIR"

TS="$(date -u +%FT%TZ)"
RESPONSE="$(curl -sS -w '\n__http_status__=%{http_code}' \
    --max-time 600 \
    -X POST "$API_URL" \
    -H "X-Admin-Key: ${ADMIN_KEY}")"
STATUS="${RESPONSE##*__http_status__=}"
BODY="${RESPONSE%__http_status__=*}"

# Compact body to one line for log-grep ergonomics.
BODY_ONELINE="$(printf '%s' "$BODY" | tr -d '\n' | tr -s ' ')"
echo "[${TS}] ${JOB} status=${STATUS} body=${BODY_ONELINE}" >> "$LOG_FILE"

if [[ "$STATUS" != 2* ]]; then
  exit 1
fi
