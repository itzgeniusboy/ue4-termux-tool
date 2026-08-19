#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO="https://github.com/itzgeniusboy/ue4-termux-tool.git"
PROJECT="$HOME/ue4-termux-tool"

fail() {
  printf '%s\n' "PakForge setup failed: $1" >&2
  exit 1
}

command -v pkg >/dev/null 2>&1 || fail "Run this command inside Termux."
printf '%s\n' "[1/4] Preparing Termux packages..."
pkg update -y
pkg install -y curl git python python-pip unzip rust

printf '%s\n' "[2/4] Enabling Android storage access..."
if command -v termux-setup-storage >/dev/null 2>&1; then
  termux-setup-storage || true
fi

if [ -d "$PROJECT/.git" ]; then
  printf '%s\n' "[3/4] Updating existing PakForge files..."
  git -C "$PROJECT" pull --ff-only || fail "Existing folder has local changes or cannot reach GitHub."
else
  if [ -e "$PROJECT" ]; then
    fail "$PROJECT exists but is not a Git checkout. Move it and run again."
  fi
  printf '%s\n' "[3/4] Downloading PakForge..."
  git clone --depth 1 "$REPO" "$PROJECT" || fail "Could not download the repository."
fi

printf '%s\n' "[4/4] Installing PakForge launcher..."
cd "$PROJECT"
chmod +x install-termux.sh ue4tool.py pakforge.py pakforge_setup.py pakforge_first_run.py update-termux.sh
PAKFORGE_DEFER_SETUP=1 SKIP_PACKAGES=1 bash install-termux.sh

printf '%s\n' ""
printf '%s\n' "PakForge is starting now; remaining setup continues in the background."
printf '%s\n' "Check progress with: pakforge setup-status"
printf '%s\n' "The compatibility wrapper remains available as: tool"
exec "${PREFIX:-/data/data/com.termux/files/usr}/bin/pakforge"
