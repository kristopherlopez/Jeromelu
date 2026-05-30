#!/usr/bin/env bash
# Run Scout S3-to-DB populate phases inside the prod API container.
#
# This is the scheduled bridge for pipelines whose admin endpoint captures raw
# Scout archives to S3 while the relational projection lives in
# scripts.data.populate_db_from_s3. It stages scripts/ and packages/ into the
# running api container, executes the existing Python orchestrator there, and
# appends status lines plus Python output to /var/log/jeromelu/scout-populate.log.
#
# Usage:
#   scout-populate.sh nrlcom-current [--seasons 2026] [--competition 111]
#   scout-populate.sh phase leaderboards [--seasons 2026] [--dry-run]
#   scout-populate.sh all [--seasons 2026] [--dry-run]
#   scout-populate.sh nrlcom-current --no-op

set -euo pipefail

NRLCOM_CURRENT_PHASES=(
  identity
  people
  rounds
  matches
  team_lists
  stats
  timeline
  standings
  leaderboards
  injuries
  reresolve
  attributes
)

KNOWN_PHASES=(
  identity
  people
  rounds
  matches
  team_lists
  stats
  timeline
  standings
  leaderboards
  injuries
  reresolve
  attributes
  player_rounds
  all
)

usage() {
  cat <<'USAGE'
Usage:
  scout-populate.sh nrlcom-current [--seasons YEAR[,YEAR...]] [--competition N] [--dry-run] [--no-op]
  scout-populate.sh phase PHASE [--seasons YEAR[,YEAR...]] [--competition N] [--dry-run] [--no-op]
  scout-populate.sh all [--seasons YEAR[,YEAR...]] [--competition N] [--dry-run] [--no-op]

Jobs:
  nrlcom-current  Project the current NRL.com S3 captures into DB tables:
                  identity, people, rounds, matches, team_lists, stats,
                  timeline, standings, leaderboards, injuries, reresolve,
                  attributes.
  phase PHASE     Run one populate_db_from_s3 phase.
  all             Run populate_db_from_s3 --phase all.

Options:
  --seasons       Space- or comma-separated season list. Defaults to UTC year.
  --competition   NRL competition id. Defaults to 111.
  --dry-run       Pass through to populate_db_from_s3 so it rolls back writes.
  --no-op         Print the plan and exit without docker/S3/DB access.

Environment overrides:
  SCOUT_API_CONTAINER      Container name, default jeromelu-api.
  SCOUT_HOST_ROOT          Host checkout root, default /opt/jeromelu.
  SCOUT_LOG_DIR            Log directory, default /var/log/jeromelu.
  SCOUT_POPULATE_RUNTMP    Container staging dir, default /runtmp/scout-populate.
USAGE
}

die() {
  echo "scout-populate: $*" >&2
  exit 2
}

contains_phase() {
  local needle="$1"
  local phase
  for phase in "${KNOWN_PHASES[@]}"; do
    [[ "$phase" == "$needle" ]] && return 0
  done
  return 1
}

join_words() {
  local item
  local first=1
  for item in "$@"; do
    if [[ "$first" -eq 1 ]]; then
      printf '%s' "$item"
      first=0
    else
      printf ' %s' "$item"
    fi
  done
}

print_shell_command() {
  local arg
  for arg in "$@"; do
    printf '%q ' "$arg"
  done
  printf '\n'
}

if [[ $# -eq 0 || "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

JOB="$1"
shift

PHASES=()
case "$JOB" in
  nrlcom-current|current)
    PHASES=("${NRLCOM_CURRENT_PHASES[@]}")
    ;;
  phase)
    [[ $# -gt 0 ]] || die "phase job requires a phase name"
    contains_phase "$1" || die "unknown phase '$1'"
    PHASES=("$1")
    shift
    ;;
  all)
    PHASES=("all")
    ;;
  *)
    die "unknown job '$JOB' (try --help)"
    ;;
esac

COMPETITION=111
SEASONS=()
DRY_RUN=0
NO_OP=0

API_CONTAINER="${SCOUT_API_CONTAINER:-jeromelu-api}"
HOST_ROOT="${SCOUT_HOST_ROOT:-/opt/jeromelu}"
LOG_DIR="${SCOUT_LOG_DIR:-/var/log/jeromelu}"
RUNTMP="${SCOUT_POPULATE_RUNTMP:-/runtmp/scout-populate}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --competition)
      [[ $# -ge 2 ]] || die "--competition requires a value"
      COMPETITION="$2"
      shift 2
      ;;
    --seasons|--season)
      shift
      [[ $# -gt 0 ]] || die "--seasons requires at least one value"
      while [[ $# -gt 0 && "${1:0:2}" != "--" ]]; do
        IFS=',' read -r -a PARTS <<< "$1"
        SEASONS+=("${PARTS[@]}")
        shift
      done
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --no-op|--print-plan)
      NO_OP=1
      shift
      ;;
    --container)
      [[ $# -ge 2 ]] || die "--container requires a value"
      API_CONTAINER="$2"
      shift 2
      ;;
    --host-root)
      [[ $# -ge 2 ]] || die "--host-root requires a value"
      HOST_ROOT="$2"
      shift 2
      ;;
    --log-dir)
      [[ $# -ge 2 ]] || die "--log-dir requires a value"
      LOG_DIR="$2"
      shift 2
      ;;
    *)
      die "unknown option '$1'"
      ;;
  esac
done

if [[ ${#SEASONS[@]} -eq 0 ]]; then
  SEASONS=("$(date -u +%Y)")
fi

[[ "$COMPETITION" =~ ^[0-9]+$ ]] || die "--competition must be numeric"
for season in "${SEASONS[@]}"; do
  [[ "$season" =~ ^[0-9]{4}$ ]] || die "--seasons values must be four-digit years"
done

case "$RUNTMP" in
  /runtmp/scout-populate|/runtmp/scout-populate/*) ;;
  *) die "SCOUT_POPULATE_RUNTMP must stay under /runtmp/scout-populate" ;;
esac

PYTHONPATH_VALUE="${RUNTMP}/packages/shared:${RUNTMP}"
LOG_FILE="${LOG_DIR}/scout-populate.log"
DRY_RUN_ARGS=()
if [[ "$DRY_RUN" -eq 1 ]]; then
  DRY_RUN_ARGS=(--dry-run)
fi

print_plan() {
  echo "Scout populate plan"
  echo "  job:         ${JOB}"
  echo "  phases:      $(join_words "${PHASES[@]}")"
  echo "  seasons:     $(join_words "${SEASONS[@]}")"
  echo "  competition: ${COMPETITION}"
  echo "  dry_run:     ${DRY_RUN}"
  echo "  container:   ${API_CONTAINER}"
  echo "  host_root:   ${HOST_ROOT}"
  echo "  runtmp:      ${RUNTMP}"
  echo "  log_file:    ${LOG_FILE}"
  echo
  echo "Would stage:"
  print_shell_command docker exec "$API_CONTAINER" rm -rf "$RUNTMP"
  print_shell_command docker exec "$API_CONTAINER" mkdir -p "$RUNTMP"
  print_shell_command docker cp "${HOST_ROOT}/scripts" "${API_CONTAINER}:${RUNTMP}/scripts"
  print_shell_command docker cp "${HOST_ROOT}/packages" "${API_CONTAINER}:${RUNTMP}/packages"
  echo
  echo "Would run:"
  local phase
  for phase in "${PHASES[@]}"; do
    print_shell_command \
      docker exec -w "$RUNTMP" -e "PYTHONPATH=${PYTHONPATH_VALUE}" "$API_CONTAINER" \
      python -m scripts.data.populate_db_from_s3 \
      --phase "$phase" --seasons "${SEASONS[@]}" --competition "$COMPETITION" "${DRY_RUN_ARGS[@]}"
  done
}

if [[ "$NO_OP" -eq 1 ]]; then
  print_plan
  exit 0
fi

mkdir -p "$LOG_DIR"

log_line() {
  echo "[$(date -u +%FT%TZ)] $*" >> "$LOG_FILE"
}

run_logged() {
  log_line "cmd=$(printf '%q ' "$@")"
  if "$@" >> "$LOG_FILE" 2>&1; then
    log_line "status=0"
  else
    local rc=$?
    log_line "status=${rc}"
    return "$rc"
  fi
}

cleanup() {
  docker exec "$API_CONTAINER" rm -rf "$RUNTMP" >> "$LOG_FILE" 2>&1 || true
}
trap cleanup EXIT

log_line "job=${JOB} phases=$(join_words "${PHASES[@]}") seasons=$(join_words "${SEASONS[@]}") competition=${COMPETITION} dry_run=${DRY_RUN} start"

run_logged docker exec "$API_CONTAINER" rm -rf "$RUNTMP"
run_logged docker exec "$API_CONTAINER" mkdir -p "$RUNTMP"
run_logged docker cp "${HOST_ROOT}/scripts" "${API_CONTAINER}:${RUNTMP}/scripts"
run_logged docker cp "${HOST_ROOT}/packages" "${API_CONTAINER}:${RUNTMP}/packages"

for phase in "${PHASES[@]}"; do
  log_line "phase=${phase} start"
  run_logged \
    docker exec -w "$RUNTMP" -e "PYTHONPATH=${PYTHONPATH_VALUE}" "$API_CONTAINER" \
    python -m scripts.data.populate_db_from_s3 \
    --phase "$phase" --seasons "${SEASONS[@]}" --competition "$COMPETITION" "${DRY_RUN_ARGS[@]}"
  log_line "phase=${phase} complete"
done

log_line "job=${JOB} complete"
