#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO="https://github.com/itzgeniusboy/ue4-termux-tool.git"
PROJECT="$HOME/ue4-termux-tool"
PREFIX_DIR="${PREFIX:-/data/data/com.termux/files/usr}"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/pakforge"
BOOTSTRAP_STATUS="$STATE_DIR/bootstrap-status.json"
BOOTSTRAP_LOG="$STATE_DIR/bootstrap.log"
BOOTSTRAP_LOCK="$STATE_DIR/bootstrap.lock"
STAGE_TOTAL=5
STARTED_EPOCH="$(date +%s)"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
HEARTBEAT_COUNT=0

if [ "${PAKFORGE_PLAIN:-0}" = "1" ] || [ "${NO_COLOR:-0}" = "1" ]; then
  PINK=""; CYAN=""; GREEN=""; YELLOW=""; RESET=""
else
  PINK="\033[1;35m"; CYAN="\033[1;36m"; GREEN="\033[1;32m"; YELLOW="\033[1;33m"; RESET="\033[0m"
fi

mkdir -p "$STATE_DIR"

write_status() {
  local state="$1"
  local message="${2:-}"
  local percent="${3:-0}"
  local stage_index="${4:-0}"
  local stage="${5:-Starting}"
  local remaining=$((100 - percent))
  HEARTBEAT_COUNT=$((HEARTBEAT_COUNT + 1))
  local updated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  local elapsed=$(( $(date +%s) - STARTED_EPOCH ))
  local eta_seconds=null
  local project_bytes=0
  if [ "$percent" -gt 0 ] && [ "$percent" -lt 100 ] && [ "$elapsed" -gt 0 ]; then
    eta_seconds=$(( elapsed * (100 - percent) / percent ))
  fi
  if [ -d "$PROJECT" ]; then
    project_bytes="$(du -sk "$PROJECT" 2>/dev/null | awk 'NR == 1 {print $1 * 1024}' || printf '0')"
    project_bytes="${project_bytes:-0}"
  fi
  local status_tmp="$BOOTSTRAP_STATUS.tmp.$$"
  printf '{"state":"%s","stage":"%s","stage_index":%s,"stage_total":%s,"percent":%s,"remaining_percent":%s,"started_at":"%s","started_epoch":%s,"updated_at":"%s","elapsed_seconds":%s,"eta_seconds":%s,"heartbeat_count":%s,"downloaded_bytes":%s,"download_total_bytes":null,"message":"%s","activity":"%s","log":"%s"}\n' \
    "$state" "$stage" "$stage_index" "$STAGE_TOTAL" "$percent" "$remaining" "$STARTED_AT" "$STARTED_EPOCH" "$updated_at" "$elapsed" "$eta_seconds" "$HEARTBEAT_COUNT" "$project_bytes" \
    "${message//\"/\\\"}" "${stage//\"/\\\"}" "${BOOTSTRAP_LOG//\"/\\\"}" > "$status_tmp"
  mv -f "$status_tmp" "$BOOTSTRAP_STATUS"
}

fail() {
  write_status failed "$1" 0 0 "Failed"
  printf '%s\n' "PakForge setup failed: $1" >> "$BOOTSTRAP_LOG"
  exit 1
}

read_field() {
  local field="$1"
  local fallback="$2"
  sed -n "s/.*\"$field\":\([0-9]*\).*/\1/p" "$BOOTSTRAP_STATUS" 2>/dev/null | head -n 1 || true
  if [ -z "$(sed -n "s/.*\"$field\":\([0-9]*\).*/\1/p" "$BOOTSTRAP_STATUS" 2>/dev/null | head -n 1)" ]; then
    printf '%s' "$fallback"
  fi
}

progress_bar() {
  local percent="${1:-0}"
  local width=28
  local filled=$((percent * width / 100))
  local empty=$((width - filled))
  printf '['
  if [ "$filled" -gt 0 ]; then printf '%*s' "$filled" '' | tr ' ' '#'; fi
  if [ "$empty" -gt 0 ]; then printf '%*s' "$empty" '' | tr ' ' '-'; fi
  printf ']'
}

format_seconds() {
  local total="${1:-0}"
  if [ "$total" = "null" ] || [ -z "$total" ]; then
    printf '%s' 'calculating'
    return
  fi
  printf '%02d:%02d:%02d' $((total / 3600)) $(((total % 3600) / 60)) $((total % 60))
}

format_bytes() {
  local bytes="${1:-0}"
  if [ "$bytes" = "null" ] || [ -z "$bytes" ]; then
    printf '%s' 'calculating'
    return
  fi
  awk -v bytes="$bytes" 'BEGIN { if (bytes < 1024) printf "%.0f B", bytes; else if (bytes < 1048576) printf "%.1f KB", bytes/1024; else if (bytes < 1073741824) printf "%.1f MB", bytes/1048576; else printf "%.2f GB", bytes/1073741824 }'
}

show_first_run() {
  local percent remaining stage state spinner elapsed eta downloaded total updated_at heartbeat
  percent="$(sed -n 's/.*\"percent\":\([0-9]*\).*/\1/p' "$BOOTSTRAP_STATUS" 2>/dev/null | head -n 1)"
  remaining="$(sed -n 's/.*\"remaining_percent\":\([0-9]*\).*/\1/p' "$BOOTSTRAP_STATUS" 2>/dev/null | head -n 1)"
  stage="$(sed -n 's/.*\"stage\":\"\([^\"]*\)\".*/\1/p' "$BOOTSTRAP_STATUS" 2>/dev/null | head -n 1)"
  state="$(sed -n 's/.*\"state\":\"\([^\"]*\)\".*/\1/p' "$BOOTSTRAP_STATUS" 2>/dev/null | head -n 1)"
  elapsed="$(sed -n 's/.*\"elapsed_seconds\":\([0-9]*\).*/\1/p' "$BOOTSTRAP_STATUS" 2>/dev/null | head -n 1)"
  eta="$(sed -n 's/.*\"eta_seconds\":\([^,]*\).*/\1/p' "$BOOTSTRAP_STATUS" 2>/dev/null | head -n 1)"
  downloaded="$(sed -n 's/.*\"downloaded_bytes\":\([0-9]*\).*/\1/p' "$BOOTSTRAP_STATUS" 2>/dev/null | head -n 1)"
  total="$(sed -n 's/.*\"download_total_bytes\":\([^,]*\).*/\1/p' "$BOOTSTRAP_STATUS" 2>/dev/null | head -n 1)"
  updated_at="$(sed -n 's/.*\"updated_at\":\"\([^\"]*\)\".*/\1/p' "$BOOTSTRAP_STATUS" 2>/dev/null | head -n 1)"
  heartbeat="$(sed -n 's/.*\"heartbeat_count\":\([0-9]*\).*/\1/p' "$BOOTSTRAP_STATUS" 2>/dev/null | head -n 1)"
  percent="${percent:-0}"
  remaining="${remaining:-100}"
  stage="${stage:-Starting}"
  state="${state:-starting}"
  elapsed="${elapsed:-0}"
  eta="${eta:-null}"
  downloaded="${downloaded:-0}"
  total="${total:-null}"
  updated_at="${updated_at:-calculating}"
  heartbeat="${heartbeat:-0}"
  spinner='|'
  case $(( $(date +%s) % 4 )) in
    1) spinner='/' ;;
    2) spinner='-' ;;
    3) spinner='\\' ;;
  esac
  printf '\033[H\033[J'
  printf '%bPakForge Launcher — OPEN%b\n' "$PINK" "$RESET"
  printf '%bFull PakForge menu is preparing automatically.%b\n\n' "$CYAN" "$RESET"
  printf 'This launcher is active now; no second command is needed.\n'
  printf '%s %3s%% stage estimate  |  %3s%% remaining  |  %s\n' "$spinner" "$percent" "$remaining" "$stage"
  progress_bar "$percent"
  printf '  %3s%%\n\n' "$percent"
  printf 'Minimum runtime and PakForge files are being prepared.\n'
  printf 'Python packages, Lua 5.1, and repak will continue after launch.\n\n'
  printf '%bState:%b %s\n' "$CYAN" "$RESET" "$state"
  printf 'Heartbeat: #%s  |  Last update: %s\n' "$heartbeat" "$updated_at"
  printf 'Elapsed: %s  |  ETA: %s\n' "$(format_seconds "$elapsed")" "$(format_seconds "$eta")"
  printf 'Download: %s / %s\n' "$(format_bytes "$downloaded")" "$(format_bytes "$total")"
  printf 'Note: package managers may not expose exact total download size.\n'
  printf 'Log: %s\n' "$BOOTSTRAP_LOG"
  printf 'The full PAK/Lua menu will open automatically when ready.\n'
}

run_with_heartbeat() {
  local label="$1"
  local start_percent="$2"
  local end_percent="$3"
  local stage_index="$4"
  shift 4
  ("$@") &
  local child="$!"
  local percent="$start_percent"
  while kill -0 "$child" 2>/dev/null; do
    write_status running "$label" "$percent" "$stage_index" "$label"
    if [ "$percent" -lt $((end_percent - 1)) ]; then
      percent=$((percent + 1))
    fi
    sleep 1
  done
  if wait "$child"; then
    write_status running "$label complete" "$end_percent" "$stage_index" "$label complete"
    return 0
  fi
  return 1
}

setup_bootstrap() {
  write_status running "Preparing Termux packages" 5 1 "Preparing Termux packages"
  printf '%s\n' "[1/4] Preparing Termux packages..."
  run_with_heartbeat "Updating Termux package lists" 5 10 1 pkg update -y || return 1
  run_with_heartbeat "Installing minimum Termux runtime" 10 20 1 pkg install -y curl git python || return 1

  write_status running "Enabling Android storage access" 25 2 "Enabling Android storage access"
  printf '%s\n' "[2/4] Enabling Android storage access..."
  if command -v termux-setup-storage >/dev/null 2>&1; then
    termux-setup-storage || true
  fi

  write_status running "Downloading PakForge repository" 35 3 "Downloading PakForge"
  if [ -d "$PROJECT/.git" ]; then
    printf '%s\n' "[3/4] Updating existing PakForge files..."
    run_with_heartbeat "Updating PakForge repository" 35 65 3 git -C "$PROJECT" pull --ff-only || return 1
  else
    if [ -e "$PROJECT" ]; then
      printf '%s\n' "PakForge directory exists but is not a Git checkout." >&2
      return 1
    fi
    printf '%s\n' "[3/4] Downloading PakForge..."
    run_with_heartbeat "Downloading PakForge repository" 35 65 3 git clone --depth 1 "$REPO" "$PROJECT" || return 1
  fi

  write_status running "Creating PakForge launcher" 75 4 "Creating PakForge launcher"
  printf '%s\n' "[4/4] Creating the PakForge launcher..."
  cd "$PROJECT"
  run_with_heartbeat "Creating PakForge launcher" 75 95 4 bash -c 'chmod +x install-termux.sh ue4tool.py pakforge.py pakforge_setup.py pakforge_first_run.py update-termux.sh && PAKFORGE_DEFER_SETUP=1 SKIP_PACKAGES=1 bash install-termux.sh' || return 1
  write_status ready "PakForge launcher is ready" 100 5 "PakForge launcher ready"
  return 0
}

if ! command -v pkg >/dev/null 2>&1; then
  fail "Run this command inside Termux so pkg can prepare the minimum runtime."
fi

lock_is_live() {
  local pid=""
  if [ -f "$BOOTSTRAP_LOCK/pid" ]; then
    pid="$(cat "$BOOTSTRAP_LOCK/pid" 2>/dev/null || true)"
  fi
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

lock_is_stale() {
  local pid="" mtime="" age=0
  if [ -f "$BOOTSTRAP_LOCK/pid" ]; then
    pid="$(cat "$BOOTSTRAP_LOCK/pid" 2>/dev/null || true)"
    [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null && return 0
    return 1
  fi
  mtime="$(stat -c %Y "$BOOTSTRAP_LOCK" 2>/dev/null || stat -f %m "$BOOTSTRAP_LOCK" 2>/dev/null || printf '0')"
  age=$(( $(date +%s) - ${mtime:-0} ))
  [ "$age" -gt 1800 ]
}

if [ -d "$BOOTSTRAP_LOCK" ] && lock_is_stale; then
  printf '%s\n' 'Removing stale PakForge bootstrap lock and recovering setup.' >> "$BOOTSTRAP_LOG"
  rm -rf "$BOOTSTRAP_LOCK"
fi

if mkdir "$BOOTSTRAP_LOCK" 2>/dev/null; then
  write_status starting "Starting background bootstrap" 0 0 "Starting bootstrap"
  (
    trap 'rm -rf "$BOOTSTRAP_LOCK"' EXIT
    if ! setup_bootstrap >> "$BOOTSTRAP_LOG" 2>&1; then
      write_status failed "See bootstrap.log for the setup error" 0 0 "Bootstrap failed"
      exit 1
    fi
  ) &
  BOOTSTRAP_PID=$!
  printf '%s\n' "$BOOTSTRAP_PID" > "$BOOTSTRAP_LOCK/pid"
else
  if lock_is_stale; then
    rm -rf "$BOOTSTRAP_LOCK"
    exec "$0" "$@"
  fi
fi

while true; do
  state="$(sed -n 's/.*\"state\":\"\([^\"]*\)\".*/\1/p' "$BOOTSTRAP_STATUS" 2>/dev/null || true)"
  case "$state" in
    ready)
      printf '%bPakForge is ready. Starting now.%b\n' "$GREEN" "$RESET"
      exec "$PREFIX_DIR/bin/pakforge"
      ;;
    failed)
      show_first_run
      printf '\n%bSetup failed. Review the log above and run bootstrap.sh again after fixing it.%b\n' "$YELLOW" "$RESET"
      exit 1
      ;;
    *)
      show_first_run
      sleep 1
      ;;
  esac
done
