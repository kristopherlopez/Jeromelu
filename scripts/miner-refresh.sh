#!/usr/bin/env bash
# Wrapper around the prod admin /api/admin/miner/* endpoints.
# Used by cron (scripts/cron.d/jeromelu) to run Miner media and data
# refresh jobs on a schedule.
#
# Usage: miner-refresh.sh {channel-stats|videos|source-discovery-youtube|supercoach-roster|supercoach-stats [ROUND|current]|supercoach-teams|supercoach-settings|nrlcom-draw|nrlcom-match-centre|nrlcom-casualty-ward|nrlcom-ladder|nrlcom-stats|nrlcom-players-roster} [--dry-run]
#
# Sources /opt/jeromelu/.env to pick up ADMIN_KEY. ALWAYS appends a
# status line to /var/log/jeromelu/miner-refresh.log — including on
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
# Use --dry-run to print the resolved admin URL without sourcing prod env or
# calling the API. Tail /var/log/jeromelu/miner-refresh.log to see recent runs.

# Note: deliberately NOT using `set -e` — we want to log the failure
# status even when curl exits non-zero. `pipefail` is fine since we
# don't have any pipelines that should swallow upstream failures.
set -uo pipefail

usage() {
  echo "usage: $0 {channel-stats|videos|source-discovery-youtube|supercoach-roster|supercoach-stats [ROUND|current]|supercoach-teams|supercoach-settings|nrlcom-draw|nrlcom-match-centre|nrlcom-casualty-ward|nrlcom-ladder|nrlcom-stats|nrlcom-players-roster} [--dry-run]" >&2
}

resolve_supercoach_round() {
  local season="$1"
  local settings_url="https://www.supercoach.com.au/${season}/api/nrl/classic/v1/settings"
  local settings_json

  settings_json="$(curl -fsS --max-time 30 "$settings_url")" || return 1
  printf '%s' "$settings_json" | python3 -c '
import json
import sys

data = json.load(sys.stdin)
round_no = data.get("competition", {}).get("current_round")
if round_no is None:
    round_no = data.get("system", {}).get("current_round")
if not isinstance(round_no, int):
    raise SystemExit("current_round missing from SuperCoach settings")
print(round_no)
'
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

DRY_RUN=0
POSITIONAL=()
for RAW_ARG in "$@"; do
  case "$RAW_ARG" in
    --dry-run) DRY_RUN=1 ;;
    *) POSITIONAL+=("$RAW_ARG") ;;
  esac
done
set -- "${POSITIONAL[@]}"
if [[ "${MINER_REFRESH_DRY_RUN:-}" == "1" ]]; then
  DRY_RUN=1
fi

JOB="${1:-}"
ARG="${2:-}"
SEASON=""

resolve_season() {
  if [[ -n "${SEASON}" ]]; then
    printf '%s\n' "$SEASON"
    return 0
  fi
  SEASON="${MINER_SEASON:-$(date -u +%Y)}"
  printf '%s\n' "$SEASON"
}

case "$JOB" in
  channel-stats) ENDPOINT="refresh-channel-stats" ;;
  videos)        ENDPOINT="refresh-videos" ;;
  source-discovery-youtube)
    DISCOVERY_MAX_RESULTS="${MINER_SOURCE_DISCOVERY_MAX_RESULTS:-10}"
    DISCOVERY_MAX_VIDEOS="${MINER_SOURCE_DISCOVERY_MAX_VIDEOS:-25}"
    DISCOVERY_MIN_SCORE="${MINER_SOURCE_DISCOVERY_MIN_SCORE:-0.55}"
    ENDPOINT="source-discovery/youtube?max_results=${DISCOVERY_MAX_RESULTS}&max_videos=${DISCOVERY_MAX_VIDEOS}&min_score=${DISCOVERY_MIN_SCORE}"
    ;;
  supercoach-roster)   ENDPOINT="supercoach-roster?season=$(resolve_season)" ;;
  supercoach-stats)
    SEASON="$(resolve_season)"
    ROUND="${ARG:-${MINER_SUPERCOACH_STATS_ROUND:-current}}"
    if [[ "$ROUND" == "current" ]]; then
      if [[ "$DRY_RUN" -eq 0 ]]; then
        ROUND="$(resolve_supercoach_round "$SEASON")"
        ROUND_RC=$?
        if [[ $ROUND_RC -ne 0 ]]; then
          LOG_DIR="${MINER_LOG_DIR:-/var/log/jeromelu}"
          LOG_FILE="${LOG_DIR}/miner-refresh.log"
          mkdir -p "$LOG_DIR"
          TS="$(date -u +%FT%TZ)"
          echo "[${TS}] ${JOB} curl_rc=${ROUND_RC} err=failed to resolve SuperCoach current_round" >> "$LOG_FILE"
          exit 1
        fi
      fi
    fi
    if [[ "$ROUND" != "current" && ! "$ROUND" =~ ^[0-9]+$ ]]; then
      echo "supercoach-stats round must be an integer or 'current'" >&2
      exit 2
    fi
    ENDPOINT="supercoach-stats?round=${ROUND}&season=${SEASON}"
    ;;
  supercoach-teams)    ENDPOINT="supercoach-teams" ;;
  supercoach-settings) ENDPOINT="supercoach-settings" ;;
  nrlcom-draw)         ENDPOINT="nrlcom-draw?competition=111&season=$(resolve_season)" ;;
  nrlcom-match-centre) ENDPOINT="nrlcom-match-centre?competition=111&season=$(resolve_season)" ;;
  nrlcom-casualty-ward) ENDPOINT="nrlcom-casualty-ward?competition=111" ;;
  nrlcom-ladder)        ENDPOINT="nrlcom-ladder?competition=111&season=$(resolve_season)" ;;
  nrlcom-stats)         ENDPOINT="nrlcom-stats?competition=111&season=$(resolve_season)" ;;
  nrlcom-players-roster) ENDPOINT="nrlcom-players-roster/refresh-all?competition=111" ;;
  *) usage; exit 2 ;;
esac

API_HOST="api.jeromelu.ai"
API_URL="https://${API_HOST}/api/admin/miner/${ENDPOINT}"
LOG_DIR="${MINER_LOG_DIR:-/var/log/jeromelu}"
LOG_FILE="${LOG_DIR}/miner-refresh.log"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "job=${JOB} api_url=${API_URL}"
  exit 0
fi

mkdir -p "$LOG_DIR"

# shellcheck disable=SC1091
. /opt/jeromelu/.env

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
