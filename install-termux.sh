#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PREFIX_DIR="${PREFIX:-/data/data/com.termux/files/usr}"
BIN_DIR="$PREFIX_DIR/bin"
CARGO_BIN_DIR="${CARGO_HOME:-$HOME/.cargo}/bin"
REPAK_CARGO_BIN="$CARGO_BIN_DIR/repak"

if [ "${SKIP_PACKAGES:-0}" = "1" ]; then
  printf '%s\n' "[1/5] Required Termux packages already prepared."
else
  printf '%s\n' "[1/5] Preparing Termux packages..."
  pkg update -y
  pkg install -y python python-pip unzip rust
fi

mkdir -p "$BIN_DIR"
if [ "${PAKFORGE_DEFER_SETUP:-0}" = "1" ]; then
  printf '%s\n' "[2/5] Deferring optional repak and Python dependencies to background setup."
else
  if command -v repak >/dev/null 2>&1; then
    printf '%s\n' "[2/5] repak is already installed."
  else
    printf '%s\n' "[2/5] Installing repak from its upstream repository..."
    cargo install --git https://github.com/trumank/repak --locked --bin repak --no-default-features
  fi

  # Cargo installs executables in ~/.cargo/bin, which is not always present in
  # an existing Termux shell PATH. Put a stable shim in $PREFIX/bin so `tool`
  # and future Termux sessions can always find the binary.
  if [ ! -x "$REPAK_CARGO_BIN" ]; then
    printf '%s\n' "Error: repak was installed but not found at $REPAK_CARGO_BIN." >&2
    exit 1
  fi
  ln -sf "$REPAK_CARGO_BIN" "$BIN_DIR/repak"
fi
export PATH="$BIN_DIR:$CARGO_BIN_DIR:$PATH"

if [ "${PAKFORGE_DEFER_SETUP:-0}" = "1" ]; then
  printf '%s\n' "[3/5] Deferring PakForge Python dependencies to background setup."
else
  printf '%s\n' "[3/5] Installing PakForge Python dependencies..."
  python3 -m pip install --upgrade rich pytz gmalg pycryptodome zstandard
fi

printf '%s\n' "[4/5] Installing tool commands..."
rm -f "$BIN_DIR/ue4tool" "$BIN_DIR/pakforge"
cat > "$BIN_DIR/tool" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
if [ "\${UE4TOOL_LEGACY:-0}" != "1" ]; then
  exec "$BIN_DIR/pakforge" "\$@"
fi
exec python3 "$SCRIPT_DIR/ue4tool.py" "\$@"
EOF
cat > "$BIN_DIR/pakforge" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
SCRIPT_DIR="$SCRIPT_DIR"
STATE_DIR="\${XDG_STATE_HOME:-\$HOME/.local/state}/pakforge"
mkdir -p "\$STATE_DIR"

SDCARD_DOWNLOAD_DIR="/sdcard/Download"
SDCARD_EDIT_DIR="\$SDCARD_DOWNLOAD_DIR/EDIT"
SDCARD_UNPACKED_DIR="\$SDCARD_DOWNLOAD_DIR/UNPACKED"
if mkdir -p "\$SDCARD_DOWNLOAD_DIR" "\$SDCARD_EDIT_DIR" "\$SDCARD_UNPACKED_DIR"; then
  printf '%s\\n' "[PakForge] SD-card folders ready: \$SDCARD_DOWNLOAD_DIR, \$SDCARD_EDIT_DIR, \$SDCARD_UNPACKED_DIR"
else
  printf '%s\\n' "[PakForge] SD-card folders could not be created. Run: termux-setup-storage" >&2
fi

UPDATE_LOG="\$STATE_DIR/update.log"
UPDATE_STATUS="\$STATE_DIR/update-status.json"
if [ "\${1:-}" = "update-status" ]; then
  if [ -f "\$UPDATE_STATUS" ]; then
    cat "\$UPDATE_STATUS"
  else
    printf '%s\n' '{"state":"not_started","message":"No startup update check has completed yet."}'
  fi
  exit 0
fi

if [ "\${PAKFORGE_NO_UPDATE:-0}" != "1" ] && [ -d "\$SCRIPT_DIR/.git" ]; then
  UPDATE_LOCK="\$STATE_DIR/update.lock"
  if mkdir "\$UPDATE_LOCK" 2>/dev/null; then
    printf '%s\n' "[PakForge] GitHub update check started in the background."
    (
      trap 'rmdir "\$UPDATE_LOCK" 2>/dev/null || true' EXIT
      cd "\$SCRIPT_DIR"
      now="\$(date -Iseconds)"
      printf '{"state":"running","time":"%s","message":"Checking origin/main"}\n' "\$now" > "\$UPDATE_STATUS"
      dirty=0
      stash_name=""
      if [ -n "\$(git status --porcelain --untracked-files=all)" ]; then
        dirty=1
        stash_name="pakforge-autoupdate-\$(date +%Y%m%d-%H%M%S)"
        if git stash push --include-untracked --message "\$stash_name" >/dev/null 2>&1; then
          printf '%s PakForge auto-stashed local changes as %s before update.\n' "\$now" "\$stash_name" >> "\$UPDATE_LOG"
        else
          printf '%s PakForge update failed: could not auto-stash local changes.\n' "\$now" >> "\$UPDATE_LOG"
          printf '{"state":"failed","time":"%s","message":"Local changes could not be backed up; current version was kept."}\n' "\$now" > "\$UPDATE_STATUS"
          exit 0
        fi
      fi
      restore_stash() {
        if [ "\$dirty" = "1" ]; then
          if git stash pop --index >/dev/null 2>&1; then
            printf '%s PakForge restored local changes after update failure.\n' "\$now" >> "\$UPDATE_LOG"
          else
            printf '%s PakForge could not automatically restore local changes; use git stash list and git stash pop.\n' "\$now" >> "\$UPDATE_LOG"
          fi
        fi
      }
      if ! git fetch --quiet origin main; then
        restore_stash
        printf '%s PakForge update failed during fetch.\n' "\$now" >> "\$UPDATE_LOG"
        printf '{"state":"failed","time":"%s","message":"GitHub fetch failed; current version was kept."}\n' "\$now" > "\$UPDATE_STATUS"
        exit 0
      fi
      before="\$(git rev-parse HEAD)"
      if git merge --ff-only --quiet origin/main; then
        after="\$(git rev-parse HEAD)"
        if [ "\$before" = "\$after" ]; then
          restore_stash
          printf '%s PakForge is already up to date.\n' "\$now" >> "\$UPDATE_LOG"
          printf '{"state":"current","time":"%s","message":"origin/main is already installed; local changes were restored."}\n' "\$now" > "\$UPDATE_STATUS"
        else
          printf '%s PakForge updated from origin/main.\n' "\$now" >> "\$UPDATE_LOG"
          if [ "\$dirty" = "1" ]; then
            printf '%s Local changes remain safely saved in git stash as %s.\n' "\$now" "\$stash_name" >> "\$UPDATE_LOG"
          fi
          printf '{"state":"updated","time":"%s","message":"Latest origin/main downloaded; local changes are preserved in git stash."}\n' "\$now" > "\$UPDATE_STATUS"
          SKIP_PACKAGES=1 PAKFORGE_DEFER_SETUP=1 bash "\$SCRIPT_DIR/install-termux.sh" >> "\$UPDATE_LOG" 2>&1 || true
        fi
      else
        backup_branch="pakforge-local-backup-\$(date +%Y%m%d-%H%M%S)"
        if git branch "\$backup_branch" "\$before" >/dev/null 2>&1 && git reset --hard origin/main >/dev/null 2>&1; then
          printf '%s PakForge reset to origin/main; previous local commits are preserved in branch %s.\n' "\$now" "\$backup_branch" >> "\$UPDATE_LOG"
          if [ "\$dirty" = "1" ]; then
            printf '%s Local uncommitted changes remain safely saved in git stash as %s.\n' "\$now" "\$stash_name" >> "\$UPDATE_LOG"
          fi
          printf '{"state":"updated","time":"%s","message":"Latest origin/main installed; local commits are preserved in %s and local edits in git stash."}\n' "\$now" "\$backup_branch" > "\$UPDATE_STATUS"
          SKIP_PACKAGES=1 PAKFORGE_DEFER_SETUP=1 bash "\$SCRIPT_DIR/install-termux.sh" >> "\$UPDATE_LOG" 2>&1 || true
        else
          restore_stash
          printf '%s PakForge update skipped: unable to synchronize origin/main safely.\n' "\$now" >> "\$UPDATE_LOG"
          printf '{"state":"skipped","time":"%s","message":"Local work was preserved; origin/main could not be synchronized safely."}\n' "\$now" > "\$UPDATE_STATUS"
        fi
      fi
    ) >/dev/null 2>&1 &
  else
    printf '%s\n' "[PakForge] GitHub update check is already running in the background."
  fi
fi

if [ "\${1:-}" = "setup-status" ]; then
  exec python3 "\$SCRIPT_DIR/pakforge_setup.py" --status
fi

SETUP_LOG="\$STATE_DIR/setup.log"
SETUP_STATUS="\$STATE_DIR/setup-status.json"
if [ "\${PAKFORGE_NO_SETUP:-0}" != "1" ] && { [ ! -f "\$SETUP_STATUS" ] || ! grep -q '"state": "ready"' "\$SETUP_STATUS" 2>/dev/null || ! python3 -c 'import rich, pytz, gmalg, Crypto, zstandard' >/dev/null 2>&1 || ! command -v repak >/dev/null 2>&1; }; then
  if [ ! -d "\$STATE_DIR/setup.lock" ]; then
    printf '%s\n' "[PakForge] Setup is running in the background. Log: \$SETUP_LOG"
    nohup python3 "\$SCRIPT_DIR/pakforge_setup.py" --background >>"\$SETUP_LOG" 2>&1 </dev/null &
  else
    printf '%s\n' "[PakForge] Background setup is already running. Log: \$SETUP_LOG"
  fi
fi

if ! python3 -c 'import rich, pytz, gmalg, Crypto, zstandard' >/dev/null 2>&1; then
  printf '%s\n' "[PakForge] Core dependencies are still installing in the background." >&2
  exec python3 "\$SCRIPT_DIR/pakforge_first_run.py" --script "\$SCRIPT_DIR/pakforge.py" "\$@"
fi

exec python3 "\$SCRIPT_DIR/pakforge.py" "\$@"
EOF
chmod 0755 "$BIN_DIR/tool" "$BIN_DIR/pakforge"

printf '%s\n' "[5/5] Verifying installation..."
if [ "${PAKFORGE_DEFER_SETUP:-0}" != "1" ]; then
  command -v repak >/dev/null 2>&1 || { printf '%s\n' "Error: repak is not available in PATH." >&2; exit 1; }
fi
command -v "$BIN_DIR/tool" >/dev/null 2>&1 || { printf '%s\n' "Error: tool command was not installed." >&2; exit 1; }
command -v "$BIN_DIR/pakforge" >/dev/null 2>&1 || { printf '%s\n' "Error: pakforge command was not installed." >&2; exit 1; }
printf '%s\n' "Done. Run: pakforge"
