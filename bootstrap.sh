#!/data/data/com.termux/files/usr/bin/sh
set -u

PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
export PREFIX
export PATH="$PREFIX/bin:/system/bin:/system/xbin:${PATH:-}"
PKG="$PREFIX/bin/pkg"
SH="$PREFIX/bin/sh"
REPO_URL="https://github.com/itzgeniusboy/pak-unpacker-termux.git"
WORK_DIR="${TMPDIR:-$HOME/.cache}/pak-unpacker-termux-bootstrap"

say() { printf '%s\n' "[pak-unpacker] $*"; }
fail() {
  printf '\n[pak-unpacker] ERROR: %s\n' "$*" >&2
  exit 1
}

if [ ! -x "$PKG" ]; then
  fail "Termux package manager was not found at $PKG. Install the official Termux app from F-Droid or the official Termux GitHub release, open it once, and run this command again."
fi

say "Checking Termux base packages..."
"$PKG" update -y || fail "Termux package update failed. Try: termux-change-repo"
"$PKG" install -y termux-tools bash curl git || fail "Could not install the basic Termux packages."

CURL="$PREFIX/bin/curl"
GIT="$PREFIX/bin/git"
BASH="$PREFIX/bin/bash"
[ -x "$CURL" ] || fail "curl is still unavailable after package installation."
[ -x "$GIT" ] || fail "git is still unavailable after package installation."
[ -x "$BASH" ] || fail "bash is still unavailable after package installation."

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
say "Downloading the latest Paktool..."
"$GIT" clone --depth 1 "$REPO_URL" "$WORK_DIR/repo" || fail "Could not download the Paktool repository. Check your internet connection."

say "Installing dependencies and commands..."
"$BASH" "$WORK_DIR/repo/install-termux.sh" || fail "Paktool installation failed. Read the message above and rerun the command after fixing it."

say "Opening the OpenCode-style PAK interface..."
exec "$PREFIX/bin/paktool-opencode"
