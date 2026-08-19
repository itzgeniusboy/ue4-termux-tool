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
  printf '{"state":"%s","stage":"%s","stage_index":%s,"stage_total":%s,"percent":%s,"remaining_percent":%s,"message":"%s","log":"%s"}\n' \
    "$state" "$stage" "$stage_index" "$STAGE_TOTAL" "$percent" "$remaining" \
    "${message//\"/\\\"}" "${BOOTSTRAP_LOG//\"/\\\"}" > "$BOOTSTRAP_STATUS"
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

show_first_run() {
  local percent remaining stage state spinner
  percent="$(sed -n 's/.*\"percent\":\([0-9]*\).*/\1/p' "$BOOTSTRAP_STATUS" 2>/dev/null | head -n 1)"
  remaining="$(sed -n 's/.*\"remaining_percent\":\([0-9]*\).*/\1/p' "$BOOTSTRAP_STATUS" 2>/dev/null | head -n 1)"
  stage="$(sed -n 's/.*\"stage\":\"\([^\"]*\)\".*/\1/p' "$BOOTSTRAP_STATUS" 2>/dev/null | head -n 1)"
  state="$(sed -n 's/.*\"state\":\"\([^\"]*\)\".*/\1/p' "$BOOTSTRAP_STATUS" 2>/dev/null | head -n 1)"
  percent="${percent:-0}"
  remaining="${remaining:-100}"
  stage="${stage:-Starting}"
  state="${state:-starting}"
  spinner='|'
  case $(( $(date +%s) % 4 )) in
    1) spinner='/' ;;
    2) spinner='-' ;;
    3) spinner='\\' ;;
  esac
  printf '\033[2J\033[H'
  printf '%bPakForge Launcher — OPEN%b\n' "$PINK" "$RESET"
  printf '%bFull PakForge menu is preparing automatically.%b\n\n' "$CYAN" "$RESET"
  printf 'This launcher is active now; no second command is needed.\n'
  printf '%s %3s%% complete  |  %3s%% remaining  |  %s\n' "$spinner" "$percent" "$remaining" "$stage"
  progress_bar "$percent"
  printf '  %3s%%\n\n' "$percent"
  printf 'Minimum runtime and PakForge files are being prepared.\n'
  printf 'Python packages, Lua 5.1, and repak will continue after launch.\n\n'
  printf '%bState:%b %s\n' "$CYAN" "$RESET" "$state"
  printf 'Log: %s\n' "$BOOTSTRAP_LOG"
  printf 'The full PAK/Lua menu will open automatically when ready.\n'
}

setup_bootstrap() {
  write_status running "Preparing Termux packages" 5 1 "Preparing Termux packages"
  printf '%s\n' "[1/4] Preparing Termux packages..."
  pkg update -y || return 1
  pkg install -y curl git python python-pip unzip rust || return 1

  write_status running "Enabling Android storage access" 25 2 "Enabling Android storage access"
  printf '%s\n' "[2/4] Enabling Android storage access..."
  if command -v termux-setup-storage >/dev/null 2>&1; then
    termux-setup-storage || true
  fi

  write_status running "Downloading PakForge repository" 45 3 "Downloading PakForge"
  if [ -d "$PROJECT/.git" ]; then
    printf '%s\n' "[3/4] Updating existing PakForge files..."
    git -C "$PROJECT" pull --ff-only || return 1
  else
    if [ -e "$PROJECT" ]; then
      printf '%s\n' "PakForge directory exists but is not a Git checkout." >&2
      return 1
    fi
    printf '%s\n' "[3/4] Downloading PakForge..."
    git clone --depth 1 "$REPO" "$PROJECT" || return 1
  fi

  write_status running "Creating PakForge launcher" 75 4 "Creating PakForge launcher"
  printf '%s\n' "[4/4] Creating the PakForge launcher..."
  cd "$PROJECT"
  chmod +x install-termux.sh ue4tool.py pakforge.py pakforge_setup.py pakforge_first_run.py update-termux.sh
  PAKFORGE_DEFER_SETUP=1 SKIP_PACKAGES=1 bash install-termux.sh || return 1
  write_status ready "PakForge launcher is ready" 100 5 "PakForge launcher ready"
  return 0
}

if ! command -v pkg >/dev/null 2>&1; then
  fail "Run this command inside Termux so pkg can prepare the minimum runtime."
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
else
  write_status running "An existing bootstrap is already running" 0 0 "Existing bootstrap is running"
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
