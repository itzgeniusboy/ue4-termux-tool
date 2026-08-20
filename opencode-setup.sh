#!/data/data/com.termux/files/usr/bin/bash
set -u

INSTALL_DIR="${PAKTOOL_DIR:-$HOME/pak-unpacker-termux}"
STATE_DIR="${PAKTOOL_STATE_DIR:-$HOME/.cache/pak-unpacker-termux}"
LOG_FILE="$STATE_DIR/setup.log"
RUNNING="$STATE_DIR/setup.running"
COMPLETE="$STATE_DIR/setup.complete"
mkdir -p "$STATE_DIR"

if [ -e "$RUNNING" ]; then
  exit 0
fi
printf '%s\n' "$$" > "$RUNNING"
trap 'rm -f "$RUNNING"' EXIT

{
  echo "[$(date)] Starting background Termux setup"
  echo "Install directory: $INSTALL_DIR"
  pkg update -y || true
  pkg install -y python python-pip git curl nodejs-lts || true

  # Never upgrade/replace Termux's protected python-pip package.
  python -m pip install --no-cache-dir rich pytz gmalg pycryptodome zstandard || true

  if command -v npm >/dev/null 2>&1 && ! command -v opencode >/dev/null 2>&1; then
    echo "Installing OpenCode CLI with npm"
    npm install --global opencode-ai@latest || true
  fi

  if command -v opencode >/dev/null 2>&1; then
    echo "OpenCode command found; native runtime check follows"
    opencode --version || echo "OpenCode exists but may not run natively on this Android device"
  else
    echo "OpenCode CLI was not installed or is not available on this device"
  fi

  echo "[$(date)] Background setup finished"
  touch "$COMPLETE"
} >> "$LOG_FILE" 2>&1
