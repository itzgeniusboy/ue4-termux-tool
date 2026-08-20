#!/data/data/com.termux/files/usr/bin/bash
set -eu

PROJECT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$PROJECT"
printf '%s\n' "Checking for Paktool updates..."

dirty=0
stash_name=""
if [ -n "$(git status --porcelain --untracked-files=all)" ]; then
  dirty=1
  stash_name="paktool-manual-update-$(date +%Y%m%d-%H%M%S)"
  git stash push --include-untracked --message "$stash_name" >/dev/null
  printf '%s\n' "Local edits saved in git stash: $stash_name"
fi

restore_stash() {
  if [ "$dirty" = "1" ]; then
    if git stash pop --index >/dev/null 2>&1; then
      printf '%s\n' "Local edits restored."
    else
      printf '%s\n' "Local edits remain in git stash; run: git stash list && git stash pop" >&2
    fi
  fi
}

before="$(git rev-parse HEAD)"
if ! git fetch --quiet origin main; then
  restore_stash
  printf '%s\n' "Update failed while contacting GitHub. The current version was kept." >&2
  exit 1
fi
if git merge --ff-only --quiet origin/main; then
  after="$(git rev-parse HEAD)"
  if [ "$before" = "$after" ]; then
    restore_stash
    printf '%s\n' "Already up to date."
    exit 0
  fi
else
  backup_branch="paktool-local-backup-$(date +%Y%m%d-%H%M%S)"
  if git branch "$backup_branch" "$before" >/dev/null 2>&1 && git reset --hard origin/main >/dev/null 2>&1; then
    printf '%s\n' "origin/main installed. Previous local commits preserved in branch: $backup_branch"
    if [ "$dirty" = "1" ]; then
      printf '%s\n' "Local edits remain safely saved in git stash: $stash_name"
    fi
    after="$(git rev-parse HEAD)"
  else
    restore_stash
    printf '%s\n' "Update skipped: local work could not be preserved safely." >&2
    exit 1
  fi
fi

printf '%s\n' "New version found. Refreshing launchers..."
chmod +x install-termux.sh paktool.py paktool_setup.py paktool_first_run.py update-termux.sh update-termux.sh paktool_setup.py paktool_first_run.py
SKIP_PACKAGES=1 PAKTOOL_DEFER_SETUP=1 bash install-termux.sh
printf '%s\n' "Update complete. Start with: paktool"
