#!/data/data/com.termux/files/usr/bin/bash
set -eu

PROJECT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$PROJECT"
printf '%s\n' "Checking for PakForge updates..."

if [ -n "$(git status --porcelain --untracked-files=all)" ]; then
  printf '%s\n' "Update skipped: local changes or untracked files detected."
  printf '%s\n' "Your files were not overwritten. Save or stash them, then retry."
  exit 0
fi

before="$(git rev-parse HEAD)"
if ! git fetch --quiet origin main; then
  printf '%s\n' "Update failed while contacting GitHub. The current version was kept." >&2
  exit 1
fi
if ! git merge --ff-only --quiet origin/main; then
  printf '%s\n' "Update skipped: fast-forward is unavailable. The current version was kept." >&2
  exit 1
fi
after="$(git rev-parse HEAD)"

if [ "$before" = "$after" ]; then
  printf '%s\n' "Already up to date."
  exit 0
fi

printf '%s\n' "New version found. Refreshing launchers..."
chmod +x install-termux.sh ue4tool.py pakforge.py update-termux.sh pakforge_setup.py pakforge_first_run.py
SKIP_PACKAGES=1 PAKFORGE_DEFER_SETUP=1 bash install-termux.sh
printf '%s\n' "Update complete. Start with: pakforge"
