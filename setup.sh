#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO="https://github.com/itzgeniusboy/ue4-termux-tool.git"
PROJECT="$HOME/ue4-termux-tool"

fail() {
  printf '%s\n' "Setup failed: $1" >&2
  printf '%s\n' "Please copy the last error message if you need help." >&2
  exit 1
}

command -v pkg >/dev/null 2>&1 || fail "This setup must run inside Termux."

printf '%s\n' "[1/5] Updating Termux packages..."
pkg update -y
pkg upgrade -y

printf '%s\n' "[2/5] Installing required packages..."
pkg install -y git python unzip rust curl

printf '%s\n' "[3/5] Requesting Android storage permission..."
if command -v termux-setup-storage >/dev/null 2>&1; then
  termux-setup-storage || true
else
  printf '%s\n' "Storage helper not available; you can still use paths inside Termux."
fi

if [ -d "$PROJECT/.git" ]; then
  printf '%s\n' "[4/5] Updating existing tool files..."
  git -C "$PROJECT" pull --ff-only || fail "Existing folder has local changes or cannot reach GitHub."
else
  printf '%s\n' "[4/5] Downloading public repository..."
  git clone "$REPO" "$PROJECT" || fail "Could not download the public repository."
fi

cd "$PROJECT"
printf '%s\n' "[5/5] Installing repak and the tool command..."
chmod +x install-termux.sh ue4tool.py update-termux.sh
SKIP_PACKAGES=1 bash install-termux.sh

export PATH="${PREFIX:-/data/data/com.termux/files/usr}/bin:$PATH"
command -v repak >/dev/null 2>&1 || fail "repak was not installed."
command -v tool >/dev/null 2>&1 || fail "tool command was not installed."

printf '%s\n' ""
printf '%s\n' "Installation complete."
printf '%s\n' "Open the tool by typing: tool"
printf '%s\n' "If Android storage permission was requested, press Allow and run tool again."
