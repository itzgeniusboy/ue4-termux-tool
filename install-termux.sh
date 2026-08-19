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
exec python3 "$SCRIPT_DIR/ue4tool.py" "\$@"
EOF
cat > "$BIN_DIR/pakforge" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
SCRIPT_DIR="$SCRIPT_DIR"
STATE_DIR="\${XDG_STATE_HOME:-\$HOME/.local/state}/pakforge"
mkdir -p "\$STATE_DIR"

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

if [ "\${PAKFORGE_NO_UPDATE:-0}" != "1" ] && [ -d "\$SCRIPT_DIR/.git" ]; then
  LOCK="\$STATE_DIR/update.lock"
  LOG="\$STATE_DIR/update.log"
  if mkdir "\$LOCK" 2>/dev/null; then
    (
      trap 'rmdir "\$LOCK" 2>/dev/null || true' EXIT
      cd "\$SCRIPT_DIR"
      git fetch --quiet origin main && git merge --ff-only --quiet origin/main \\
        && printf '%s PakForge updated in background\\n' "\$(date -Iseconds)" >> "\$LOG" \\
        || true
    ) >/dev/null 2>&1 &
  fi
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
