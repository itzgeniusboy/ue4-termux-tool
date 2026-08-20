#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_URL="https://github.com/itzgeniusboy/pak-unpacker-termux.git"
WORK_DIR="${TMPDIR:-$HOME/.cache}/pak-unpacker-termux-bootstrap"
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"

if command -v git >/dev/null 2>&1; then
  git clone --depth 1 "$REPO_URL" "$WORK_DIR/repo"
  bash "$WORK_DIR/repo/install-termux.sh"
else
  pkg update -y
  pkg install -y git
  git clone --depth 1 "$REPO_URL" "$WORK_DIR/repo"
  bash "$WORK_DIR/repo/install-termux.sh"
fi
