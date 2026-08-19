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
      if [ -n "\$(git status --porcelain --untracked-files=no)" ]; then
        printf '%s PakForge update skipped: local changes detected.\n' "\$now" >> "\$UPDATE_LOG"
        printf '{"state":"skipped","time":"%s","message":"Local changes detected; no files were overwritten."}\n' "\$now" > "\$UPDATE_STATUS"
        exit 0
      fi
      if ! git fetch --quiet origin main; then
        printf '%s PakForge update failed during fetch.\n' "\$now" >> "\$UPDATE_LOG"
        printf '{"state":"failed","time":"%s","message":"GitHub fetch failed; current version was kept."}\n' "\$now" > "\$UPDATE_STATUS"
        exit 0
      fi
      if git merge --ff-only --quiet origin/main; then
        printf '%s PakForge updated from origin/main.\n' "\$now" >> "\$UPDATE_LOG"
        printf '{"state":"updated","time":"%s","message":"Latest origin/main downloaded; it will be active on the next launch."}\n' "\$now" > "\$UPDATE_STATUS"
        SKIP_PACKAGES=1 PAKFORGE_DEFER_SETUP=1 bash "\$SCRIPT_DIR/install-termux.sh" >> "\$UPDATE_LOG" 2>&1 || true
      else
        printf '%s PakForge update skipped: fast-forward unavailable.\n' "\$now" >> "\$UPDATE_LOG"
        printf '{"state":"skipped","time":"%s","message":"Fast-forward unavailable; current version was kept."}\n' "\$now" > "\$UPDATE_STATUS"
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
