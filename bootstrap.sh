#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO="https://github.com/itzgeniusboy/ue4-termux-tool.git"
PROJECT="$HOME/ue4-termux-tool"
PREFIX_DIR="${PREFIX:-/data/data/com.termux/files/usr}"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/pakforge"
BOOTSTRAP_STATUS="$STATE_DIR/bootstrap-status.json"
BOOTSTRAP_LOG="$STATE_DIR/bootstrap.log"
BOOTSTRAP_LOCK="$STATE_DIR/bootstrap.lock"

if [ "${PAKFORGE_PLAIN:-0}" = "1" ] || [ "${NO_COLOR:-0}" = "1" ]; then
  PINK=""; CYAN=""; GREEN=""; YELLOW=""; RESET=""
else
  PINK="\033[1;35m"; CYAN="\033[1;36m"; GREEN="\033[1;32m"; YELLOW="\033[1;33m"; RESET="\033[0m"
fi

mkdir -p "$STATE_DIR"

write_status() {
  local state="$1"
  local message="${2:-}"
  printf '{"state":"%s","message":"%s","log":"%s"}\n' \
    "$state" "${message//\"/\\\"}" "${BOOTSTRAP_LOG//\"/\\\"}" > "$BOOTSTRAP_STATUS"
}

fail() {
  write_status failed "$1"
  printf '%s\n' "PakForge setup failed: $1" >> "$BOOTSTRAP_LOG"
  exit 1
}

show_first_run() {
  printf '\033[2J\033[H'
  printf '%bPakForge%b\n' "$PINK" "$RESET"
  printf '%bFirst-time setup is running in the background.%b\n\n' "$CYAN" "$RESET"
  printf 'The launcher will open automatically as soon as the minimum files are ready.\n'
  printf 'Python packages, Lua 5.1, and repak will continue installing after launch.\n\n'
  printf '%bStatus:%b %s\n' "$CYAN" "$RESET" "$(sed -n 's/.*\"state\":\"\([^\"]*\)\".*/\1/p' "$BOOTSTRAP_STATUS" 2>/dev/null || printf 'starting')"
  printf 'Log: %s\n' "$BOOTSTRAP_LOG"
  printf 'You can leave this screen open; it will hand off automatically.\n'
}

setup_bootstrap() {
  write_status running "Preparing Termux prerequisites"
  printf '%s\n' "[1/4] Preparing Termux packages..."
  pkg update -y || return 1
  pkg install -y curl git python python-pip unzip rust || return 1

  printf '%s\n' "[2/4] Enabling Android storage access..."
  if command -v termux-setup-storage >/dev/null 2>&1; then
    termux-setup-storage || true
  fi

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

  printf '%s\n' "[4/4] Creating the PakForge launcher..."
  cd "$PROJECT"
  chmod +x install-termux.sh ue4tool.py pakforge.py pakforge_setup.py pakforge_first_run.py update-termux.sh
  PAKFORGE_DEFER_SETUP=1 SKIP_PACKAGES=1 bash install-termux.sh || return 1
  write_status ready "PakForge launcher is ready"
  return 0
}

if ! command -v pkg >/dev/null 2>&1; then
  fail "Run this command inside Termux so pkg can prepare the minimum runtime."
fi

if mkdir "$BOOTSTRAP_LOCK" 2>/dev/null; then
  write_status starting "Starting background bootstrap"
  (
    trap 'rm -rf "$BOOTSTRAP_LOCK"' EXIT
    if ! setup_bootstrap >> "$BOOTSTRAP_LOG" 2>&1; then
      write_status failed "See bootstrap.log for the setup error"
      exit 1
    fi
  ) &
else
  write_status running "An existing bootstrap is already running"
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
