#!/data/data/com.termux/files/usr/bin/bash
set -eu

REPO="https://github.com/itzgeniusboy/ue4-termux-tool.git"
PROJECT="$HOME/ue4-termux-tool"

printf '%s\n' "[1/4] Preparing Termux packages..."
pkg update -y
pkg install -y git python unzip rust
termux-setup-storage || true

if [ -d "$PROJECT/.git" ]; then
  printf '%s\n' "[2/4] Updating existing tool..."
  git -C "$PROJECT" pull --ff-only
else
  printf '%s\n' "[2/4] Downloading public repository..."
  git clone "$REPO" "$PROJECT"
fi

cd "$PROJECT"
printf '%s\n' "[3/4] Building and installing repak..."
chmod +x install-termux.sh ue4tool.py update-termux.sh
bash install-termux.sh

printf '%s\n' "[4/4] Installation complete."
printf '%s\n' "Run: ue4tool"
printf '%s\n' "Or check commands with: ue4tool --help"
