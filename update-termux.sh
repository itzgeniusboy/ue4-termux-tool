#!/data/data/com.termux/files/usr/bin/bash
set -eu

PROJECT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$PROJECT"
printf '%s\n' "Checking for tool updates..."
before="$(git rev-parse HEAD)"
git pull --ff-only
after="$(git rev-parse HEAD)"

if [ "$before" = "$after" ]; then
  printf '%s\n' "Already up to date."
  exit 0
fi

printf '%s\n' "New version found. Installing changes..."
chmod +x install-termux.sh ue4tool.py update-termux.sh
bash install-termux.sh
printf '%s\n' "Update complete."
