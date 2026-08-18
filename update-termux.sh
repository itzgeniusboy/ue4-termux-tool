#!/data/data/com.termux/files/usr/bin/bash
set -eu

PROJECT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$PROJECT"
printf '%s\n' "Updating UE4 Termux Tool..."
git pull --ff-only
chmod +x install-termux.sh ue4tool.py update-termux.sh
bash install-termux.sh
printf '%s\n' "Update complete. Run: ue4tool"
