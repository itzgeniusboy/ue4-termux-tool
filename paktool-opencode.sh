#!/data/data/com.termux/files/usr/bin/bash
set -u

INSTALL_DIR="${PAKTOOL_DIR:-$HOME/pak-unpacker-termux}"
STATE_DIR="${PAKTOOL_STATE_DIR:-$HOME/.cache/pak-unpacker-termux}"
LOG_FILE="$STATE_DIR/setup.log"
mkdir -p "$STATE_DIR"

if [ ! -f "$INSTALL_DIR/paktool_ui.py" ]; then
  echo "Paktool installation not found at: $INSTALL_DIR"
  echo "Run the installer first:"
  echo "curl -fsSL https://raw.githubusercontent.com/itzgeniusboy/pak-unpacker-termux/main/bootstrap.sh | bash"
  exit 1
fi

# Setup runs in the background so the UI is available immediately.
if [ ! -f "$STATE_DIR/setup.complete" ] && [ ! -e "$STATE_DIR/setup.running" ]; then
  nohup bash "$INSTALL_DIR/opencode-setup.sh" >/dev/null 2>&1 &
fi

export PAKTOOL_SETUP_LOG="$LOG_FILE"
export PAKTOOL_AUTO_AUTH=1
exec python "$INSTALL_DIR/paktool_ui.py"
