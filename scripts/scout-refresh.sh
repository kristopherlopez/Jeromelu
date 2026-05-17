#!/usr/bin/env bash
# Wrapper around the prod admin /api/admin/scout/refresh-* endpoints.
# Used by cron (scripts/cron.d/jeromelu) to refresh channel and video
# metrics on a schedule.
#
# Usage: scout-refresh.sh {channel-stats|videos}
#
# Sources /opt/jeromelu/.env to pick up ADMIN_KEY. ALWAYS appends a
# status line to /var/log/jeromelu/scout-refresh.log — including on
# curl-level failures (timeout, DNS, connection refused) that cause
# curl to exit non-zero. Without that, the prior `set -e` made cron
# failures invisible: curl would error, the script would die before
# the log line, and nothing surfaced.
#
# Returns non-zero on either curl failure or non-2xx HTTP so cron /
# external monitoring can detect failure.
#
# Routes via --resolve to 127.0.0.1 because Lightsail does not hairpin-
# NAT — sending a packet to api.jeromelu.ai (52.65.91.199) from the
# box's own egress IP just times out. Caddy in the same compose stack
# answers fine on loopback with the right Host header.
#
# Tail /var/log/jeromelu/scout-refresh.log to see recent runs.

# Note: deliberately NOT using `set -e` — we want to log the failure
# status even when curl exits non-zero. `pipefail` is fine since we
# don't have any pipelines that should swallow upstream failures.
set -uo pipefail

JOB="${1:-}"
case "$JOB" in
  channel-stats) ENDPOINT="refresh-channel-stats" ;;
  videos)        ENDPOINT="refresh-videos" ;;
  *) echo "usage: $0 {channel-stats|videos}" >&2; exit 2 ;;
esac

# shellcheck disable=SC1091
. /opt/jeromelu/.env

API_HOST="api.jeromelu.ai"
API_URL="https://${API_HOST}/api/admin/scout/${ENDPOINT}"
LOG_DIR="/var/log/jeromelu"
LOG_FILE="${LOG_DIR}/scout-refresh.log"

mkdir -p "$LOG_DIR"

TS="$(date -u +%FT%TZ)"
# --max-time 3600: the videos job typically runs 13–20 min server-side (~2400
# videos.list batches × ~0.3s + identity-sync UPDATEs, all committed in one
# transaction at the end), but slow YouTube-API nights have pushed it to ~45
# min. The previous 900s ceiling triggered curl_rc=28 nightly even when the
# server-side work succeeded. 1 hour is well under the 24h cron interval.
RESPONSE="$(curl -sS -w '\n__http_status__=%{http_code}' \
    --max-time 3600 \
    --resolve "${API_HOST}:443:127.0.0.1" \
    -X POST "$API_URL" \
    -H "X-Admin-Key: ${ADMIN_KEY}" 2>&1)"
CURL_RC=$?

if [[ $CURL_RC -ne 0 ]]; then
  # curl failed at the transport layer — no HTTP response. Log the
  # exit code + whatever curl wrote (its error message lands on stderr,
  # captured via 2>&1 above) so the cause is recoverable.
  ERR_ONELINE="$(printf '%s' "$RESPONSE" | tr -d '\n' | tr -s ' ')"
  echo "[${TS}] ${JOB} curl_rc=${CURL_RC} err=${ERR_ONELINE}" >> "$LOG_FILE"
  exit 1
fi

STATUS="${RESPONSE##*__http_status__=}"
BODY="${RESPONSE%__http_status__=*}"

# Compact body to one line for log-grep ergonomics.
BODY_ONELINE="$(printf '%s' "$BODY" | tr -d '\n' | tr -s ' ')"
echo "[${TS}] ${JOB} status=${STATUS} body=${BODY_ONELINE}" >> "$LOG_FILE"

if [[ "$STATUS" != 2* ]]; then
  exit 1
fi
